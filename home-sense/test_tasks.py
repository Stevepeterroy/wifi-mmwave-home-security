import unittest
from unittest.mock import patch
from integrations import GoogleTasks,task_payloads
TRIAL={'id':'trial-a','name':'Polycam','start':'2026-10-01','days':7,'status':'Active Trial'}
class TaskTests(unittest.TestCase):
 def test_dates_status_and_supported_fields(self):
  rows=task_payloads(TRIAL);self.assertEqual([r['due'][:10] for r in rows],['2026-10-05','2026-10-06','2026-10-07','2026-10-08'])
  self.assertTrue(all(set(r)=={'title','notes','due','status'} for r in rows));self.assertTrue(all(r['status']=='needsAction' for r in task_payloads({**TRIAL,'status':'Cancellation Pending'})))
 def test_repeat_sync_reuses_server_ids_and_pages(self):
  rows=task_payloads(TRIAL);calls=[]
  def call(path,method='GET',body=None):
   calls.append((path,method,body))
   if method=='GET':
    if 'pageToken=' in path:return {'items':[{'id':'t'+str(i),'notes':r['notes']} for i,r in enumerate(rows[2:],2)]}
    return {'items':[{'id':'t'+str(i),'notes':r['notes']} for i,r in enumerate(rows[:2])],'nextPageToken':'page2'}
   return {'id':path[1:]}
  adapter=GoogleTasks('test-token');adapter.call=call
  result=adapter.sync(TRIAL);self.assertEqual(len(result),4);self.assertEqual(sum(m=='PATCH' for _,m,_ in calls),4);self.assertFalse(any(m=='POST' for _,m,_ in calls))
 def test_verified_cancellation_completes_only_existing_tasks(self):
  rows=task_payloads(TRIAL)
  adapter=GoogleTasks('test-token')
  with patch.object(adapter,'call',side_effect=[{'items':[{'id':'t1','notes':rows[0]['notes']}]},{'id':'t1'}]) as call:
   result=adapter.sync({**TRIAL,'status':'Cancelled & Verified'});self.assertEqual(result,[{'id':'t1','state':'completed'}]);self.assertEqual(call.call_args.args[2]['status'],'completed')
 def test_insertion_disables_ambiguous_retry_and_missing_credentials_fail(self):
  with patch('integrations.request_json',return_value={'id':'created'}) as request:
   GoogleTasks('token').call('','POST',{});self.assertFalse(request.call_args.kwargs['retry'])
  with patch.dict('os.environ',{},clear=True):
   with self.assertRaises(ValueError):GoogleTasks().call('')
if __name__=='__main__':unittest.main()
