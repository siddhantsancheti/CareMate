"""
Database storage layer (Supabase Postgres)
------------------------------------------
A thin wrapper over psycopg. It only saves and loads rows; it never answers
app queries (our data structures in dsa/ do that).

Connection details come from supabase_config.ini (copy supabase_config.example.ini).
If that file is missing, the app runs fully in memory.
"""

import configparser
import os
import threading

import psycopg
from psycopg.rows import dict_row

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "supabase_config.ini")
SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")


class Database:
    def __init__(self, url, schema="public"):
        self.name = schema
        self._url = url
        self._schema = schema
        self._lock = threading.Lock()   # one shared connection + lock; a connection pool would suit many users
        self._conn = None
        self._connect()
        if schema != "public":          # tests use their own schema so real data is never touched
            self._run(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        with open(SCHEMA_FILE, encoding="utf-8") as f:
            sql = "\n".join(line.split("--")[0] for line in f)   # drop '-- comments'
        for stmt in sql.split(";"):                               # schema has no ';' in strings
            if stmt.strip():
                self._run(stmt)

    def _connect(self):
        self._conn = psycopg.connect(self._url, autocommit=True, row_factory=dict_row,
                                     prepare_threshold=None,   # needed behind Supabase's pooler
                                     options=f"-c search_path={self._schema}")

    def _run(self, sql, params=None):
        # Table/column names below are fixed in our code; VALUES always go through
        # %s placeholders, so user input can never inject SQL.
        with self._lock:
            if self._conn.closed:                      # reconnect after a dropped connection
                self._connect()
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall() if cur.description else []

    def insert(self, table, row, ignore=False):
        cols = ", ".join(row)
        marks = ", ".join(["%s"] * len(row))
        self._run(f"INSERT INTO {table} ({cols}) VALUES ({marks})"
                  f"{' ON CONFLICT DO NOTHING' if ignore else ''}", list(row.values()))

    def update(self, table, fields, **where):
        sets = ", ".join(f"{k} = %s" for k in fields)
        cond = " AND ".join(f"{k} = %s" for k in where)
        self._run(f"UPDATE {table} SET {sets} WHERE {cond}", [*fields.values(), *where.values()])

    def delete(self, table, **where):
        cond = " AND ".join(f"{k} = %s" for k in where)
        self._run(f"DELETE FROM {table} WHERE {cond}", list(where.values()))

    def all(self, table):
        return self._run(f"SELECT * FROM {table}")

    def close(self):
        self._conn.close()

    def is_empty(self):
        return self._run("SELECT COUNT(*) AS n FROM patients")[0]["n"] == 0


def read_url():
    """The connection string from supabase_config.ini, or None."""
    if not os.path.exists(CONFIG_FILE):
        return None
    cfg = configparser.ConfigParser(interpolation=None)   # passwords may contain '%'
    cfg.read(CONFIG_FILE)
    return cfg["supabase"].get("url", "").strip() or None


def connect_from_config():
    """Returns a Database, or None if there is no config (in-memory mode)."""
    url = None if os.environ.get("CAREMATE_NO_DB") else read_url()
    return Database(url) if url else None
