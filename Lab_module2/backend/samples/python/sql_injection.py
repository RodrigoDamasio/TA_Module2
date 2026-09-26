"""User lookup for the admin dashboard."""

import sqlite3


def find_user(conn: sqlite3.Connection, username: str):
    query = f"SELECT id, email FROM users WHERE username = '{username}'"
    return conn.execute(query).fetchone()


def count_users(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
