import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()

class DBHelper:
    def __init__(self):
        self.host = os.getenv("DB_HOST")
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASS")
        self.database = os.getenv("DB_NAME")
        self.connection = None

    def connect(self, database=None):
        """Establish a connection to the database."""
        db_to_use = database if database is not None else self.database
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=db_to_use if db_to_use else None,
                connect_timeout=10
            )
            if self.connection.is_connected():
                return self.connection
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            return None

    def execute_query(self, query, params=None, fetch=True):
        """Execute a query and return results."""
        if not self.connection or not self.connection.is_connected():
            self.connect()
        
        if not self.connection:
            return None

        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params or ())
            if fetch:
                result = cursor.fetchall()
                return result
            self.connection.commit()
            return True
        except Error as e:
            print(f"Query Error: {e}")
            return None
        finally:
            cursor.close()

    def close(self):
        """Close the database connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()

    def get_active_proxies(self) -> list[dict]:
        """Fetch all active proxies from the database."""
        # Note: 'stauts' matches the typo in your DB schema
        query = "SELECT id, ip, port, username, password FROM proxy WHERE stauts = 'active'"
        rows = self.execute_query(query)
        return rows if rows else []

    def update_proxy_status(self, proxy_id: int, alive: bool):
        """Update the status of a proxy (active/dead)."""
        status = "active" if alive else "dead"
        query = "UPDATE proxy SET stauts = %s WHERE id = %s"
        self.execute_query(query, (status, proxy_id), fetch=False)

if __name__ == "__main__":
    # Test Discovery
    db = DBHelper()
    # Connect without a specific database to see what's available
    conn = db.connect(database="") 
    if conn:
        print("Connected successfully! Discovering databases...")
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        dbs = cursor.fetchall()
        print("Available Databases:")
        for (name,) in dbs:
            print(f" - {name}")
        conn.close()
