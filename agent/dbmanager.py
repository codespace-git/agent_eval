import sqlite3
import threading
import contextlib



class AgentDataBaseManager:
    def __init__(self, state_db_path="", network_db_path=""):
        self.state_db_path = state_db_path
        self.network_db_path = network_db_path
        self.state_lock = threading.Lock() 
        self.network_lock = threading.Lock()

    
    def init_dbs(self):
        
        with self.get_state_connection() as conn:
            conn.executescript("""
                PRAGMA JOURNAL_MODE = WAL;

                CREATE TABLE IF NOT EXISTS control (
                    id INTEGER PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    data_size INTEGER DEFAULT 1,
                    inject INTEGER DEFAULT 0
                );

                INSERT OR IGNORE INTO control (id, count, data_size, inject) 
                VALUES (1, 0, 1, 0);
                PRAGMA JOURNAL_MODE = WAL;

                CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                old_value INTEGER,
                new_value INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed INTEGER DEFAULT 0
            );
        """)
        
       
        with self.get_network_connection() as conn:
            conn.executescript("""
                PRAGMA JOURNAL_MODE = WAL;
                
                CREATE TABLE IF NOT EXISTS NETWORK (
                    id INTEGER PRIMARY KEY,
                    prompt_attempt INTEGER DEFAULT 0,
                    start TEXT DEFAULT NULL
                    inject_prev DEFAULT 0,
                    inject_next DEFAULT 0,
                    fail_count DEFAULT 0
                );
                INSERT OR IGNORE INTO NETWORK (id, prompt_attempt, start, inject_prev, inject_next, fail_count) 
                VALUES (1, 0, NULL, 0, 0, 0);
            """)

    
    @contextlib.contextmanager
    def get_state_connection(self):
       
        with self.state_lock: 
            conn = sqlite3.connect(self.state_db_path, timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            try:
                yield conn  
            finally:
                conn.close()  
    
    @contextlib.contextmanager
    def get_network_connection(self):
        
        with self.network_lock:
            conn = sqlite3.connect(self.network_db_path, timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            try:
                yield conn
            finally:
                conn.close()
    
    @contextlib.contextmanager
    def transaction(self):
        
        try:
           with self.get_network_connection() as conn:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
        except Exception:
            conn.rollback()
            raise


    def update_control_inject(self, inject_value):
       
        with self.get_state_connection() as conn:
            conn.execute("UPDATE control SET inject = ? WHERE id = 1", (inject_value,))
            conn.commit()
    
    def update_control_count(self, count):
        
        with self.get_state_connection() as conn:
            conn.execute("UPDATE control SET count = ? WHERE id = 1", (count,))
            conn.commit()
    
    def set_data_size(self, size):
       
        with self.get_state_connection() as conn:
            conn.execute("UPDATE control SET data_size = ? WHERE id = 1", (size,))
            conn.commit()
    
    def get_network_state(self):
        
        with self.get_network_connection() as conn: 
            return conn.execute("SELECT prompt_attempt, start FROM NETWORK WHERE id = 1")
           
    
    def set_network_config(self, tool_limit, prompt_limit, prob):
        
        with self.get_network_connection() as conn:
            conn.execute("UPDATE NETWORK SET tool_limit = ?, prompt_limit = ?, prob = ? WHERE id = 1", (tool_limit, prompt_limit, prob,))
            conn.commit()
    
    def update_prompt_attempt(self, attempt):
    
        with self.get_network_connection() as conn:
            conn.execute("UPDATE NETWORK SET prompt_attempt = ? WHERE id = 1", (attempt,))
            conn.commit()
    
    def update_network_start(self, start_time):
       
        with self.get_network_connection() as conn:
            conn.execute("UPDATE NETWORK SET start = ? WHERE id = 1", (start_time,))
            conn.commit()
    
    def fetch_event_status(self):
        with self.get_state_connection() as conn:
           cursor = conn.cursor()
           cursor.execute("SELECT NOT EXISTS (SELECT 1 FROM events WHERE event_type = 'inject_changed' AND processed = 1)")
           no_pending_events = cursor.fetchone()[0]
           return no_pending_events
    
    def signal_exit(self):
        with self.get_state_connection() as conn:
            conn.execute("UPDATE CONTROL SET count = data_size WHERE id = 1")
            conn.commit()

    def get_injection_state(self):
        with self.get_network_connection() as conn:
            return conn.execute("SELECT inject_prev, inject_next, fail_count FROM NETWORK WHERE id = 1")
        
    
    def update_injection_state(self,prev,succ,count):
        with self.transaction() as conn:
            conn.execute("UPDATE NETWORK SET inject_prev = ?, inject_next = ?, fail_count = ? WHERE id = 1", (prev, succ, count,))



