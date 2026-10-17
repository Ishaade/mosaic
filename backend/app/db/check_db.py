"""List tables in mosaic.db. Always run from backend/ so the path is correct."""
import sqlite3

conn = sqlite3.connect("mosaic.db")
rows = conn.execute("select name from sqlite_master where type='table'").fetchall()
print("tables:", rows)
conn.close()
