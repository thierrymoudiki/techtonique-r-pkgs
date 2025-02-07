#!/bin/bash
sqlite3 database.db "CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package TEXT,
    timestamp TEXT,
    ip TEXT
);"
