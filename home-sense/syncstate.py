"""Durable integration outcomes, separate from browser-editable home settings."""
import sqlite3,json,time,uuid
from contextlib import contextmanager
class SyncStore:
 def __init__(self,path):self.path=path
 @contextmanager
 def connection(self):
  db=sqlite3.connect(self.path() if callable(self.path) else self.path)
  db.execute('CREATE TABLE IF NOT EXISTS integration_sync (trial TEXT, provider TEXT, value TEXT, PRIMARY KEY(trial,provider))')
  try:
   with db:yield db
  finally:db.close()
 def begin(self,trial,provider):
  value={'trialId':trial['id'],'provider':provider,'attemptId':uuid.uuid4().hex,'state':'pending','at':time.time(),'trialStatus':trial['status'],'start':trial['start'],'days':trial['days']}
  with self.connection() as db:db.execute('INSERT OR REPLACE INTO integration_sync VALUES (?,?,?)',(trial['id'],provider,json.dumps(value)))
  return value
 def finish(self,attempt,results=None,error=None):
  value={**attempt,'state':'failed' if error else 'synced','at':time.time()}
  if error:value['error']=str(error)
  else:value['results']=results
  with self.connection() as db:
   old=db.execute('SELECT value FROM integration_sync WHERE trial=? AND provider=?',(attempt['trialId'],attempt['provider'])).fetchone()
   if old and json.loads(old[0])['attemptId']==attempt['attemptId']:db.execute('UPDATE integration_sync SET value=? WHERE trial=? AND provider=?',(json.dumps(value),attempt['trialId'],attempt['provider']))
  return value
 def list(self):
  with self.connection() as db:return [json.loads(row[0]) for row in db.execute('SELECT value FROM integration_sync')]
