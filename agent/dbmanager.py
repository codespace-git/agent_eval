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
                CREATE TABLE IF NOT EXISTS control (
                    id INTEGER PRIMARY KEY,
                    count INTEGER DEFAULT 0,
                    data_size INTEGER DEFAULT 1,
                    inject INTEGER DEFAULT 0
                );
                INSERT OR IGNORE INTO control (id, count, data_size, inject) 
                VALUES (1, 0, 1, 0);
                PRAGMA JOURNAL_MODE = WAL;
            """)
        
       
        with self.get_network_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS NETWORK (
                    id INTEGER PRIMARY KEY,
                    tool_limit INTEGER DEFAULT 1,
                    prompt_limit INTEGER DEFAULT 1,
                    prompt_attempt INTEGER DEFAULT 0,
                    prob REAL DEFAULT 0.1,
                    start TEXT DEFAULT NULL
                );
                INSERT OR IGNORE INTO NETWORK (id, tool_limit, prompt_limit, prompt_attempt, prob, start) 
                VALUES (1, 1, 1, 0, 0.1, NULL);
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
            cursor = conn.cursor()  
            cursor.execute("SELECT tool_limit, prompt_limit, prompt_attempt, prob, start FROM NETWORK WHERE id = 1")
            row = cursor.fetchone()
            return row 
    
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
    











