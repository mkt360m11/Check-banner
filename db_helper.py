import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
# Find the absolute path to the .env file in the same directory as this script
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

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
            print(f"Error connecting to MySQL: {e} (Host: {self.host})")
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

    # ── Generic CRUD Utilities ────────────────────────────────────────────────

    def get_all(self, table_name: str) -> list[dict]:
        """Fetch all records from a specified table."""
        query = f"SELECT * FROM {table_name}"
        return self.execute_query(query)

    def get_filtered(self, table_name: str, filters: dict) -> list[dict]:
        """Fetch records with basic filtering. 'filters' is {column: value}."""
        where_clause = " AND ".join([f"{col} = %s" for col in filters.keys()])
        query = f"SELECT * FROM {table_name} WHERE {where_clause}"
        return self.execute_query(query, tuple(filters.values()))

    def get_by_id(self, table_name: str, record_id: int) -> dict | None:
        """Fetch a single record by its ID."""
        query = f"SELECT * FROM {table_name} WHERE id = %s"
        rows = self.execute_query(query, (record_id,))
        return rows[0] if rows else None

    def add_record(self, table_name: str, data: dict) -> bool:
        """Insert a new record into a table. 'data' is a dict of {column: value}."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        return self.execute_query(query, tuple(data.values()), fetch=False)

    def update_record(self, table_name: str, record_id: int, data: dict) -> bool:
        """Update an existing record by ID."""
        set_clause = ", ".join([f"{col} = %s" for col in data.keys()])
        query = f"UPDATE {table_name} SET {set_clause} WHERE id = %s"
        params = tuple(data.values()) + (record_id,)
        return self.execute_query(query, params, fetch=False)

    def delete_record(self, table_name: str, record_id: int) -> bool:
        """Delete a record from a table by ID."""
        query = f"SELECT id FROM {table_name} WHERE id = %s" # Check existence
        if not self.execute_query(query, (record_id,)):
            return False
        
        query = f"DELETE FROM {table_name} WHERE id = %s"
        return self.execute_query(query, (record_id,), fetch=False)

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
