package main

import (
	"database/sql"
	"log"
	"time"
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

func main() {
	
	toxiClient := toxiproxy.NewClient(base_client_URL)
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		log.Fatalf("DB error: %v,exiting now", err)
	}
	defer db.Close()
	
	createTable(db)

	var (
		searchProxy     *toxiproxy.Proxy
		weatherProxy    *toxiproxy.Proxy
		movieProxy      *toxiproxy.Proxy
		calendarProxy   *toxiproxy.Proxy
		calculatorProxy *toxiproxy.Proxy
		messageProxy    *toxiproxy.Proxy
		translatorProxy *toxiproxy.Proxy
	)

	for{
		
	searchProxy, err = toxiClient.CreateProxy("search_proxy", "0.0.0.0:6000", "search_tool:5000")
	if err != nil {
		log.Printf("search_proxy failed: %v", err)
		continue
	}
	break
}
	for{
		
	weatherProxy, err = toxiClient.CreateProxy("weather_proxy", "0.0.0.0:6001", "weather_tool:5001")
	if err != nil {
		log.Printf("weather_proxy failed: %v", err)
		continue
	}
	break
	}
	for{
		
	movieProxy, err = toxiClient.CreateProxy("movie_proxy", "0.0.0.0:6002", "movie_tool:5002")
	if err != nil {
		log.Printf("movie_proxy failed: %v", err)
		continue
	}
	break
}
	for{
	calendarProxy, err = toxiClient.CreateProxy("calendar_proxy", "0.0.0.0:6003", "calendar_tool:5003")
	if err != nil {
		log.Printf("calendar_proxy failed: %v", err)
		continue
	}
	break
	}
	for{
		
	calculatorProxy, err = toxiClient.CreateProxy("calculator_proxy", "0.0.0.0:6004", "calculator_tool:5004")
	if err != nil {
		log.Printf("calculator_proxy failed: %v", err)
		continue
	}
	break
}
	for{
		
	messageProxy, err = toxiClient.CreateProxy("message_proxy", "0.0.0.0:6005", "message_tool:5005")
	if err != nil {
		log.Printf("message_proxy failed: %v", err)
		continue
	}
	break
}

	for{
		
		translatorProxy, err = toxiClient.CreateProxy("translator_proxy", "0.0.0.0:6006", "translator_tool:5006")
	if err != nil {
		log.Printf("translator_proxy failed: %v", err)
		continue
	}
	break
}
	_ = searchProxy
	_ = weatherProxy
	_ = movieProxy
	_ = calendarProxy
	_ = calculatorProxy
	_ = messageProxy
	_ = translatorProxy

	for {
		count, limit := getState(db)

		switch {
		case count==limit:
			deleteProxies(toxiClient)
			log.Println("service no longer required,exiting now")
			return 
		case count%10 == 9:
			time.Sleep(time.Second)
			injectToxics(toxiClient)
		case count == -1:
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
			data_size INTEGER 
		);
		INSERT OR IGNORE INTO control (id, count, data_size) VALUES (1, 0, 0);
	`)
	
	if err!=nil{
		log.Printf("error creating table: %v",err)
		continue
	}
	
		log.Printf("table created")
		break
	
  }
}


func getState(db *sql.DB) (int, int) {
	var count, limit int
	err := db.QueryRow("SELECT count, data_size FROM control WHERE id = 1").Scan(&count, &limit)
	if err != nil {
		log.Printf("DB fetch error: %v", err)
		return 0,0
	}
	return count, limit
}

func injectToxics(client *toxiproxy.Client) {
	for _, cfg := range proxyConfig {
		proxy, err := client.Proxy(cfg.Name)
		if err != nil {
			log.Printf("Error fetching proxy %s: %v", cfg.Name, err)
			continue
		}
		proxy.AddToxic("timeout_toxic", "timeout", "downstream", 1.0, toxiproxy.Attributes{"timeout": 5000})
	}
}

func removeToxics(client *toxiproxy.Client) {
	for _, cfg := range proxyConfig {
		proxy, err := client.Proxy(cfg.Name)
		if err != nil {
			log.Printf("Error fetching proxy %s for toxic removal: %v", cfg.Name, err)
			continue
		}
		proxy.RemoveToxic("timeout_toxic")
		}
	}


func deleteProxies(client *toxiproxy.Client) {
	for _, cfg := range proxyConfig {
	
		proxy, err := client.Proxy(cfg.Name)
		if err != nil {
			log.Printf("Error fetching proxy %s for toxic removal: %v", cfg.Name, err)
			continue
		}
		proxy.Delete()
		log.Printf("Deleted proxy %s", cfg.Name)
		
	}
}
