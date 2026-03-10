import sqlite3
import os
import json
import pandas as pd

CACHE_DB_PATH = "data/cache/trade_cache.db"

class TradeCacheDB:
    def __init__(self, db_path=CACHE_DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 台灣 Top10 快取表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS taiwan_top10 (
                    year INTEGER PRIMARY KEY,
                    top_n INTEGER,
                    top_items_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # BACI 處理記錄狀態表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS baci_trade_status (
                    year INTEGER PRIMARY KEY,
                    num_records INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
    def get_taiwan_top10(self, year: int, top_n: int) -> list[str] | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT top_items_json FROM taiwan_top10 WHERE year = ? AND top_n = ?", (year, top_n))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
            
    def set_taiwan_top10(self, year: int, top_n: int, top_items: list[str]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO taiwan_top10 (year, top_n, top_items_json) VALUES (?, ?, ?)",
                (year, top_n, json.dumps(top_items))
            )

    def get_taiwan_df(self, year: int) -> pd.DataFrame | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (f"taiwan_df_{year}",))
            if cursor.fetchone():
                return pd.read_sql(f"SELECT * FROM taiwan_df_{year}", conn)
            return None

    def set_taiwan_df(self, year: int, df: pd.DataFrame):
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql(f"taiwan_df_{year}", conn, if_exists="replace", index=False)

    def get_baci(self, year: int) -> pd.DataFrame | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM baci_trade_status WHERE year = ?", (year,))
            if cursor.fetchone():
                try:
                    return pd.read_sql(f"SELECT * FROM baci_trade_{year}", conn)
                except Exception:
                    return None
            return None

    def set_baci(self, year: int, df: pd.DataFrame):
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql(f"baci_trade_{year}", conn, if_exists="replace", index=False)
            conn.execute(
                "INSERT OR REPLACE INTO baci_trade_status (year, num_records) VALUES (?, ?)",
                (year, len(df))
            )

cache_db = TradeCacheDB()
