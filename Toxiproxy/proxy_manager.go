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
    "net/http"
    
    toxiproxy "github.com/Shopify/toxiproxy/v2/client"
    _ "modernc.org/sqlite"
)

const (
    dbPath = "./state/state.db"
    baseClientURL = "toxiproxy:8474"
    maxtries = 3
    timeout_up = 4000
    timeout_down = 4000
    eventPollInterval = 100 * time.Millisecond
    baseDelay = 100 * time.Millisecond
    healthCheckPort = ":8000" 
    maxerrorinstances = 15
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

type Event struct {
    ID        int
    EventType string
    OldValue  int
    NewValue  int
    Timestamp string
    Processed int
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
        PRAGMA journal_mode=WAL;
        
        CREATE TABLE IF NOT EXISTS control (
            id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0,
            data_size INTEGER DEFAULT 1,
            inject INTEGER DEFAULT 0
        );

        INSERT OR IGNORE INTO control (id, count, data_size, inject) 
        VALUES (1, 0, 1, 0);

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            old_value INTEGER,
            new_value INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed INTEGER DEFAULT 0
        );
        
        CREATE TRIGGER IF NOT EXISTS inject_change_trigger
        AFTER UPDATE OF inject ON control
        WHEN NEW.inject != OLD.inject
        BEGIN
            INSERT INTO events (event_type, old_value, new_value)
            VALUES ('inject_changed', OLD.inject, NEW.inject);
        END;	
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



func (ps *ProxyService) getState() (int, int, error) {
    count, size := 0, 1

    err := ps.retryOperation(func() error {
        return ps.db.QueryRow("SELECT count, data_size FROM control WHERE id = 1").
        Scan(&count, &size)
    })

    return count, size, err
}


func (ps *ProxyService) getEvents() ([]Event, error) {
    var events []Event
    
    err := ps.retryOperation(func() error {
       
        tx, err := ps.db.Begin()
        if err != nil {
            return fmt.Errorf("failed to begin transaction: %w", err)
        }
        defer tx.Rollback()


        rows, err := tx.Query(`
            SELECT id, event_type, old_value, new_value, timestamp, processed 
            FROM events 
            ORDER BY timestamp ASC
        `)
        if err != nil {
            return err
        }
        defer rows.Close()
        
        events = nil 
        var err error
        for rows.Next() {
            var event Event
            var err error
            err = rows.Scan(&event.ID, &event.EventType, &event.OldValue, 
                           &event.NewValue, &event.Timestamp, &event.Processed)
            if err != nil {
                return err
            }
            events = append(events, event)
        }
        
        if err = rows.Err(); err != nil {
            return err
        }

     
        return tx.Commit()
    })
    
    return events, err
}
func (ps *ProxyService) removeEvents(eventID int) error {
    return ps.retryOperation(func() error {
        _, err := ps.db.Exec("DELETE FROM events WHERE id = ?", eventID)
        return err
    })
}
func (ps *ProxyService) processEvents() error {
    events, err := ps.getEvents()
    if err != nil {
        return fmt.Errorf("failed to fetch events: %w", err)
    }
    if len(events) == 0 {
        return nil 
    }   

    var err error
    for _, event := range events {
        if event.Processed == 0 {
            log.Printf("Processing event: %v", event)
            switch event.EventType {
            case "inject_changed":
                if event.NewValue == 1 {
                    ps.injectToxics()
            } else {
                ps.removeToxics()
            }
            default:
                log.Printf("Unknown event type: %s", event.EventType)
        }
        var err error
        err = ps.retryOperation(func() error {
            var err error
            _, err = ps.db.Exec("UPDATE events SET processed = 1 WHERE id = ?", event.ID)
            return err
        })
        if err != nil {
            log.Printf("Failed to mark event %d as processed: %v", event.ID, err)
        }
    }

        if err = ps.removeEvents(event.ID); err != nil {
            log.Printf("Failed to remove event %d: %v", event.ID, err)
        }
        
    }
    return nil
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

func (ps *ProxyService) Run(var errorcount int) error {
    if err := ps.createProxies(); err != nil {
        return fmt.Errorf("failed to create proxies: %w", err)
    }
    if errorcount != 0{
        errorcount = 0
    }
    log.Println("Proxy service started successfully")
    
    for {
        select {
        case <-ps.ctx.Done():
            log.Println("Shutting down proxy service...")
            ps.deleteProxies()
            return nil
            
        default:
            if err := ps.processEvents(); err != nil {
                log.Printf("Failed to process events: %v", err)
                errorcount++
                if errorcount >= maxerrorcount{
                    ps.deleteProxies()
                    return fmt.Errorf("error limit reached")
                }
            }

            count, size, err := ps.getState()
            if err != nil {
                return fmt.Errorf("failed to fetch state of db: %w",err)
            }
            if count == size {
                ps.deleteProxies()
                log.Println("Service no longer required, exiting now")
                return nil
            }
        }
        time.Sleep(eventPollInterval)
    }
}

func (ps *ProxyService) Close() {
    ps.cancel()
    ps.db.Close()
}

func startHealthServer(ctx context.Context) {
    http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusOK)
        w.Write([]byte("OK"))
    })
    
    server := &http.Server{Addr: healthCheckPort}
    
    go func() {
        log.Printf("HealthCheckServer running on port %s",healthCheckPort)
        if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            log.Printf("Health check server error: %v", err)
        }
    }()

    go func() {
        <-ctx.Done()
        log.Println("Shutting down health check server...")
        shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
        defer cancel()
        server.Shutdown(shutdownCtx)
    }()
}

func main() {
    ps, err := NewProxyService()
    if err != nil {
        log.Fatalf("Failed to create proxy service: %v", err)
        os.exit(1)
    }
    defer ps.Close()
    
   startHealthServer(ps.ctx)

    c := make(chan os.Signal, 1)
    signal.Notify(c, os.Interrupt, syscall.SIGTERM)
    
    go func() {
        sig := <-c
        log.Println("Received shutdown signal")
        ps.Close()
        os.Exit(0)
    }()
    
    errorinstances := 0
    if err := ps.Run(errorinstances); err != nil {
        log.Fatalf("Proxy service failed: %v", err)
        os.exit(1)
    }
    os.exit(0)
}