import sqlite3,tempfile,unittest
from pathlib import Path
from database import connection
class DatabaseTests(unittest.TestCase):
 def test_commit_and_close(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'db.sqlite'
   with connection(path) as db:db.execute('CREATE TABLE rows (value INTEGER)');db.execute('INSERT INTO rows VALUES (1)')
   with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')
   with connection(path) as reopened:self.assertEqual(reopened.execute('SELECT value FROM rows').fetchone()[0],1)
 def test_error_rolls_back_and_closes(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'db.sqlite'
   with connection(path) as db:db.execute('CREATE TABLE rows (value INTEGER)')
   with self.assertRaises(ValueError):
    with connection(path) as db:db.execute('INSERT INTO rows VALUES (1)');raise ValueError('Failed operation')
   with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')
   with connection(path) as reopened:self.assertEqual(reopened.execute('SELECT COUNT(*) FROM rows').fetchone()[0],0)
if __name__=='__main__':unittest.main()
