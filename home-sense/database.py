"""A transaction context that also closes its SQLite connection."""
import sqlite3
from contextlib import contextmanager
@contextmanager
def connection(path):
 db=sqlite3.connect(path)
 try:
  with db:yield db
 finally:db.close()
