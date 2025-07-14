package main

import (
	"database/sql"
	"log"
	"time"
	"math/rand"
	toxiproxy "github.com/Shopify/toxiproxy/v2/client"
	_ "modernc.org/sqlite"
)

const (
	dbPath  = "./state/state.db"
	base_client_URL = "toxiproxy:8474"
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
toxics := []struct {
    Name   string
    Type   string
    Stream string
}{
    {"timeout_toxic_down", "timeout", "downstream"},
    {"timeout_toxic_up", "timeout", "upstream"},
}


func main() {
	
	toxiClient := toxiproxy.NewClient(base_client_URL)
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		log.Fatalf("DB error: %v,exiting now", err)
	}
	defer db.Close()
	
	createTable(db)

for _, cfg := range proxyConfig {
    for {
        _, err := toxiClient.CreateProxy(cfg.Name, cfg.Listen, cfg.Upstream)
        if err != nil {
            continue
        }
        break
    }
}

	

	for {
		time.Sleep(time.Second)
		count, size, inject:= getState(db)

		switch {
		case count==size:
			deleteProxies(toxiClient)
			log.Println("service no longer required,exiting now")
			return 
		case inject == 1:
			
			injectToxics(toxiClient)
			
		case inject == 0:
			
			removeToxics(toxiClient)
			
		
		}
	}
}

func createTable(db *sql.DB) {
	for{
	_, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS control (
			id INTEGER PRIMARY KEY,
			count INTEGER ,
			data_size INTEGER ,
			inject INTEGER 
		);
		INSERT OR IGNORE INTO control (id, count, data_size,inject) VALUES (1, 0, 0, 0);
	`)
	
	if err!=nil{
		log.Printf("error creating table: %v",err)
		continue
	}
	
		log.Printf("table created")
		break
	
  }
}


func getState(db *sql.DB) (int, int, int) {
	var count, size, inject int
	for{
	err := db.QueryRow("SELECT count, data_size, inject FROM control WHERE id = 1").Scan(&count, &size,&inject)
	if err != nil {
		log.Printf("DB fetch error: %v", err)
		continue
	}
	break
  }
	return count, size, inject

}


func removeToxicsForProxy(proxy *toxiproxy.Proxy) {
	
	if _, err := proxy.Toxic("toxic_timeout_up"); err == nil {
		 proxy.RemoveToxic("toxic_timeout_up")
	}

	   
	if _, err := proxy.Toxic("toxic_timeout_down"); err == nil {
		 proxy.RemoveToxic("toxic_timeout_down")
	}
}

func injectToxics(client *toxiproxy.Client) {
	for _, cfg := range proxyConfig {
		proxy, err := client.Proxy(cfg.Name)
		if err != nil {
			continue
		}
		removeToxicsForProxy(proxy)
		if rand.Intn(2) == 0 {
		proxy.AddToxic("toxic_timeout_up", "timeout", "upstream", 1.0, toxiproxy.Attributes{"timeout": 5000})
		}
		else {
		proxy.AddToxic("toxic_timeout_down", "timeout", "downstream", 1.0, toxiproxy.Attributes{"timeout": 5000})
		}
		proxy.Save()
		
}
}

func removeToxics(client *toxiproxy.Client) {
	for _, cfg := range proxyConfig {
		proxy, err := client.Proxy(cfg.Name)
		if err != nil {
			continue
		}
		removeToxicsForProxy(proxy)
		proxy.Save()
		
		}
	}


func deleteProxies(client *toxiproxy.Client) {
	for _, cfg := range proxyConfig {
	
		proxy, err := client.Proxy(cfg.Name)
		if err != nil {
			continue
		}
		proxy.Delete()	
		
	}
}
