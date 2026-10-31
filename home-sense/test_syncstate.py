import unittest,tempfile
from pathlib import Path
from syncstate import SyncStore
class SyncTests(unittest.TestCase):
 def test_pending_success_and_failure_survive_restart(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'state.sqlite';store=SyncStore(path);trial={'id':'t','status':'Active Trial','start':'2026-10-01','days':7}
   attempt=store.begin(trial,'tasks');self.assertEqual(SyncStore(path).list()[0]['state'],'pending')
   store.finish(attempt,results=[{'id':'external-task'}]);self.assertEqual(SyncStore(path).list()[0]['state'],'synced')
   attempt=store.begin(trial,'calendar');store.finish(attempt,error='Authorization unavailable');records=SyncStore(path).list();self.assertEqual({r['provider']:r['state'] for r in records},{'tasks':'synced','calendar':'failed'})
 def test_old_attempt_cannot_overwrite_newer_outcome(self):
  with tempfile.TemporaryDirectory() as folder:
   store=SyncStore(Path(folder)/'state.sqlite');trial={'id':'t','status':'Active Trial','start':'2026-10-01','days':7}
   old=store.begin(trial,'tasks');new=store.begin(trial,'tasks');store.finish(new,results=[]);store.finish(old,error='late failure');self.assertEqual(store.list()[0]['attemptId'],new['attemptId']);self.assertEqual(store.list()[0]['state'],'synced')
if __name__=='__main__':unittest.main()
