package main

import (
    "database/sql"
    "log"
    "time"
    "math/rand"
    "os"
    "os/signal"
    "syscall"
    "context"
    "fmt"
    
    toxiproxy "github.com/Shopify/toxiproxy/v2/client"
    _ "modernc.org/sqlite"
)

const (
    dbPath = "./state/state.db"
    baseClientURL = "toxiproxy:8474"
    maxtries = 4
    baseDelay = time.Second
    timeout_up = 4000
    timeout_down = 4000
)

var proxyConfig = []struct {
    Name     string
    Listen   string
    Upstream string
}{
    {"search_proxy", "0.0.0.0:6000", "search_tool:5000"},
    {"weather_proxy", "0.0.0.0:6001", "weather_tool:5001"},
    {"movie_proxy", "0.0.0.0:6002", "movie_tool:5002"},
    {"calendar_proxy", "0.0.0.0:6003", "calendar_tool:5003"},
    {"calculator_proxy", "0.0.0.0:6004", "calculator_tool:5004"},
    {"message_proxy", "0.0.0.0:6005", "message_tool:5005"},
    {"translator_proxy", "0.0.0.0:6006", "translator_tool:5006"},
}
var toxics = []string{"toxic_timeout_up", "toxic_timeout_down"}

type ProxyService struct {
    client *toxiproxy.Client
    db     *sql.DB
    ctx    context.Context
    cancel context.CancelFunc
}

func retryOperation(operation func() error) error {
    for i := 0; i < maxtries; i++ {
        if err := operation(); err == nil {
            return nil
        }
        
        if i < maxtries-1 {
            time.Sleep(baseDelay * time.Duration(1<<i))
        }
    }
    return fmt.Errorf("operation failed after %d retries", maxtries)
}

func NewProxyService() (*ProxyService, error) {
    var db *sql.DB
    if err := retryOperation(func() error {
        var err error
        db, err = sql.Open("sqlite", dbPath)
        return err
    }); err != nil {
        return nil, fmt.Errorf("failed to connect with db: %w", err)
    }
    
    
    
    ctx, cancel := context.WithCancel(context.Background())
    client := toxiproxy.NewClient(baseClientURL)
    ps := &ProxyService{
        client: client,
        db:     db,
        ctx:    ctx,
        cancel: cancel,
    }
    
    if err := ps.initializeDatabase(); err != nil {
        return nil, fmt.Errorf("failed to initialize database: %w", err)
    }
    
    return ps, nil
}

func (ps *ProxyService) retryOperation(operation func() error) error {
    for i := 0; i < maxtries; i++ {
        if err := operation(); err == nil {
            return nil
        }
        
        if i < maxtries-1 {
            time.Sleep(baseDelay * (1<<i)) 
        }
    }
    return fmt.Errorf("operation failed after %d retries", maxtries)
}

func (ps *ProxyService) initializeDatabase() error {
    query := `
        CREATE TABLE IF NOT EXISTS control (
            id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0,
            data_size INTEGER DEFAULT 1,
            inject INTEGER DEFAULT 0
        );
        INSERT OR IGNORE INTO control (id, count, data_size, inject) 
        VALUES (1, 0, 1, 0);
		PRAGMA journal_mode=WAL;
    `
    
    return ps.retryOperation(func() error {
        _, err := ps.db.Exec(query)
        return err
    })
}



func (ps *ProxyService) createProxies() error {
    for _, cfg := range proxyConfig {
        err := ps.retryOperation(func() error {
            var err error
            _, err = ps.client.CreateProxy(cfg.Name, cfg.Listen, cfg.Upstream)
            return err
        })
        if err != nil {
            return fmt.Errorf("failed to create proxy %s: %w", cfg.Name, err)
        }
    }
    return nil
}

func (ps *ProxyService) getState() (int, int, int, error) {
    count, size, inject := 0, 1, 0

    err := ps.retryOperation(func() error {
        return ps.db.QueryRow("SELECT count, data_size, inject FROM control WHERE id = 1").
        Scan(&count, &size, &inject)
    })
    
    return count, size, inject, err
}

func (ps *ProxyService) getDynamicInterval(count, size int) time.Duration {
    switch {
    case count == 0:
        return 500* time.Millisecond
    case count == size:
        return 100 * time.Millisecond 
    default:
        return 2 * baseDelay
    }
}

func (ps *ProxyService) removeToxicsForProxy(proxy *toxiproxy.Proxy) {
       
    for _, toxic := range toxics {
        
		err := ps.retryOperation(func() error {

			return proxy.RemoveToxic(toxic)
		})
		if err != nil {
			log.Printf("Failed to remove toxic %s from proxy %s: %v", toxic, proxy.Name, err)
			continue
		}
       
            proxy.Save()
            log.Printf("removed toxic %s from proxy %s", toxic, proxy.Name)
        
    }
}

func (ps *ProxyService) injectToxics() {
    for _, cfg := range proxyConfig {
        var proxy *toxiproxy.Proxy
		err := ps.retryOperation(func() error {
            var err error
            
        proxy, err = ps.client.Proxy(cfg.Name)
        return err
		})
		if err != nil {
			log.Printf("Failed to get proxy %s: %v", cfg.Name, err)
			continue
		}

        
        ps.removeToxicsForProxy(proxy)

        hasToxic := false
        for _, toxic := range toxics {
            if _, err := proxy.Toxic(toxic); err == nil {
                hasToxic = true
            }
        }
    
    if !hasToxic {
        var err error
        if rand.Intn(2) == 0 {
            err = ps.retryOperation(func() error {
                var err error
                _, err = proxy.AddToxic("toxic_timeout_up", "timeout", "upstream", 1.0,
                    toxiproxy.Attributes{"timeout": timeout_up})
                return err
            })
        } else {
            err = ps.retryOperation(func() error {
                var err error
                _, err = proxy.AddToxic("toxic_timeout_down", "timeout", "downstream", 1.0,
                    toxiproxy.Attributes{"timeout": timeout_down})
                return err
            })
        }
        if err != nil {
            log.Printf("Failed to add toxic to proxy %s: %v", cfg.Name, err)
            continue
        }
        proxy.Save()
    }
}
}


func (ps *ProxyService) removeToxics() {
    for _, cfg := range proxyConfig {
        var proxy *toxiproxy.Proxy
		err := ps.retryOperation(func() error {
        var err error
        proxy, err = ps.client.Proxy(cfg.Name)
        return err
		})
		if err != nil {
			log.Printf("Failed to get proxy %s: %v", cfg.Name, err)
			continue
		}
        
        ps.removeToxicsForProxy(proxy)
        
    }
}

func (ps *ProxyService) deleteProxies() {
	
    for _, cfg := range proxyConfig {
        var proxy *toxiproxy.Proxy
		err := ps.retryOperation(func() error {
			var err error
			proxy, err = ps.client.Proxy(cfg.Name)
			return err
		})
		if err != nil {
			log.Printf("Failed to get proxy %s: %v", cfg.Name, err)
			continue
		}
        proxy.Delete()
        log.Printf("deleted proxy %s",proxy.Name)
    }
}

func (ps *ProxyService) Run() error {
    if err := ps.createProxies(); err != nil {
        return fmt.Errorf("failed to create proxies: %w", err)
    }
    
    log.Println("Proxy service started successfully")
    
    for {
        select {
        case <-ps.ctx.Done():
            log.Println("Shutting down proxy service...")
            ps.deleteProxies()
            return nil
            
        default:
            count, size, inject, err := ps.getState()
            if err != nil {
                return fmt.Errorf("failed to fetch state of db: %w",err)
            }
            
            switch {
            case count == size:
                ps.deleteProxies()
                log.Println("Service no longer required, exiting now")
                return nil
                
            case inject == 1:
                ps.injectToxics()
                log.Println("Toxics injected")
                
            case inject == 0:
                ps.removeToxics()
                log.Println("Toxics removed")
            }
            
            interval := ps.getDynamicInterval(count, size)
            time.Sleep(interval)
        }
    }
}

func (ps *ProxyService) Close() {
    ps.cancel()
    ps.db.Close()
}

func main() {
    ps, err := NewProxyService()
    if err != nil {
        log.Fatalf("Failed to create proxy service: %v", err)
    }
    defer ps.Close()
    
   
    c := make(chan os.Signal, 1)
    signal.Notify(c, os.Interrupt, syscall.SIGTERM)
    
    go func() {
        <-c
        log.Println("Received shutdown signal")
        ps.Close()
        os.Exit(0)
    }()
    
    if err := ps.Run(); err != nil {
        log.Fatalf("Proxy service failed: %v", err)
    }
}