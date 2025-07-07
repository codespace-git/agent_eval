package main

import (
	"database/sql"
	"log"
	"time"
	"github.com/Shopify/toxiproxy/v2/client"
	_ "modernc.org/sqlite"
)

const (
	dbPath  = "./state/state.db"
	base_client_URL = "http://toxiproxy:8474"
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

func main() {
	client := client.NewClient(base_client_URL)
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		log.Fatalf("DB error: %v,exiting now", err)
	}
	defer db.Close()
	
	createTable(db)
}
	
	for _, cfg := range proxyConfig {
		_, err := client.CreateProxy(cfg.Name, cfg.Listen, cfg.Upstream)
		if err != nil && !client.IsConflict(err) {
			log.Printf("Failed to create proxy %s: %v", cfg.Name, err)
			continue
		}
	}

	for {
		time.Sleep(time.Second)

		count, limit := getState(db)

		switch {
		case count==limit:
			deleteProxies(client)
			log.Println("service no longer required,exiting now")
			return 
		case count%10 == 9:
			injectToxics(client)
		case count == -1:
			removeToxics(client)
		
		}
	}
}

func createTable(db *sql.DB) {
	_, err := db.Exec(`
		CREATE TABLE control (
			id INTEGER PRIMARY KEY,
			count INTEGER ,
			limit INTEGER 
		);
		INSERT OR IGNORE INTO control (id, count, limit) VALUES (1, 0, 0);
	`)
	if err!=nil{
		log.Printf("error creating table: %v",err)
	
}

func getState(db *sql.DB) (int, int) {
	var count, limit int
	err := db.QueryRow("SELECT count, limit FROM control WHERE id = 1").Scan(&count, &limit)
	if err != nil {
		log.Printf("DB fetch error: %v", err)
		return 0,0
	}
	return count, limit
}

func injectToxics(client *client.Client) {
	for _, cfg := range proxyConfig {
		proxy, err := client.Proxy(cfg.Name)
		if err != nil {
			log.Printf("Error fetching proxy %s: %v", cfg.Name, err)
			continue
		}
		_, err = proxy.AddToxic("timeout_toxic", "timeout", "downstream", 1.0, client.Attributes{"timeout": 5000})
		if err == nil {
			log.Printf("Injected toxic into %s", cfg.Name)
		}
	}
}

func removeToxics(client *client.Client) {
	for _, cfg := range proxyConfig {
		proxy, err := client.Proxy(cfg.Name)
		if err != nil {
			log.Printf("Error fetching proxy %s for toxic removal: %v", cfg.Name, err)
			continue
		}
		err = proxy.RemoveToxic("timeout_toxic")
		if err == nil {
			log.Printf("Removed toxic from %s", cfg.Name)
		}
	}
}

func deleteProxies(client *client.Client) {
	for _, cfg := range proxyConfig {
		err := client.DeleteProxy(cfg.Name)
		if err != nil {
			log.Printf("Failed to delete proxy %s: %v", cfg.Name, err)
			continue 
		} else {
			log.Printf("Deleted proxy %s", cfg.Name)
		}
	}
}
