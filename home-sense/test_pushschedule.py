import tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from webpush import PushStore
from pushschedule import PushScheduler
from test_webpush import subscription
NOW=datetime(2026,10,5,10,tzinfo=timezone.utc).timestamp()
TRIAL={'id':'trial-a','name':'Trial','start':'2026-10-01','days':7,'status':'Active Trial','proof':'','repeatMinutes':5}
class ScheduleTests(unittest.TestCase):
 def fixture(self,folder):
  store=PushStore(Path(folder)/'push.sqlite');store.subscribe(subscription());return store,PushScheduler(store)
 def test_repeat_is_durable_and_deduplicated(self):
  with tempfile.TemporaryDirectory() as folder:
   store,scheduler=self.fixture(folder);home={'trials':[TRIAL]};scheduler.tick(home,NOW);scheduler.tick(home,NOW+1)
   self.assertEqual(store.summary()['states'],{'pending':1});PushScheduler(PushStore(Path(folder)/'push.sqlite')).tick(home,NOW+301);self.assertEqual(store.summary()['states'],{'pending':2})
 def test_pending_continues_verified_cancels_queued_messages(self):
  with tempfile.TemporaryDirectory() as folder:
   store,scheduler=self.fixture(folder);scheduler.tick({'trials':[{**TRIAL,'status':'Cancellation Pending'}]},NOW);self.assertEqual(store.summary()['states'],{'pending':1})
   scheduler.tick({'trials':[{**TRIAL,'status':'Cancelled & Verified','proof':'receipt'}]},NOW+301);self.assertEqual(store.summary()['states'],{'cancelled':1});calls=[];store.deliver(lambda s,p:calls.append(p) or 201,NOW+400);self.assertEqual(calls,[])
 def test_before_window_and_removed_trials_do_not_notify(self):
  with tempfile.TemporaryDirectory() as folder:
   store,scheduler=self.fixture(folder);scheduler.tick({'trials':[TRIAL]},NOW-86400);self.assertEqual(store.summary()['states'],{})
   scheduler.tick({'trials':[TRIAL]},NOW);scheduler.tick({'trials':[]},NOW+1);self.assertEqual(store.summary()['states'],{'cancelled':1})
if __name__=='__main__':unittest.main()
