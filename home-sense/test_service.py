from database import connection
import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import server
from integrations import calendar_payloads,GoogleCalendar,Polycam

class PersistenceTests(unittest.TestCase):
 def test_stale_home_save_cannot_remove_paired_sensor(self):
  with tempfile.TemporaryDirectory() as folder:
   old=server.DB;server.DB=Path(folder)/'test.sqlite3'
   try:
    with connection(server.DB) as db:
     db.execute('CREATE TABLE config (id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
     db.execute('CREATE TABLE device_bindings (module TEXT PRIMARY KEY,device TEXT UNIQUE NOT NULL)')
     db.execute('INSERT INTO device_bindings VALUES (?,?)',('paired','esp-1'))
    saved={'rooms':[],'modules':[{'id':'paired','name':'Radar'}],'events':[]}
    server.save_config(saved)
    with self.assertRaisesRegex(ValueError,'Forget the ESP pairing'):
     server.save_config({'rooms':[],'modules':[],'events':[]})
    self.assertEqual(server.get_config()['modules'],saved['modules'])
    with connection(server.DB) as db:db.execute('DELETE FROM device_bindings WHERE module=?',('paired',))
    server.save_config({'rooms':[],'modules':[],'events':[]})
    self.assertEqual(server.get_config()['modules'],[])
   finally:server.DB=old

 def test_save_restart_and_invalid_dimensions(self):
  with tempfile.TemporaryDirectory() as folder:
   old=server.DB;server.DB=Path(folder)/'test.sqlite3'
   try:
    import sqlite3
    with connection(server.DB) as db:db.execute('CREATE TABLE config (id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
    cfg={'rooms':[{'x':0,'z':0,'width':4,'depth':3}],'modules':[],'events':[],'profile':'Test'}
    server.save_config(cfg);self.assertEqual(server.get_config(),cfg)
    cfg['rooms'][0]['width']=0
    with self.assertRaises(ValueError):server.save_config(cfg)
    self.assertEqual(server.get_config()['rooms'][0]['width'],4)
   finally:server.DB=old

 def test_stale_settings_write_preserves_server_event_and_review(self):
  with tempfile.TemporaryDirectory() as folder:
   old=server.DB;server.DB=Path(folder)/'test.sqlite3'
   try:
    import sqlite3
    with connection(server.DB) as db:db.execute('CREATE TABLE config (id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
    event={'id':'live-1','at':'2026-10-09T01:00:00Z','acknowledged':True,'source':'live'}
    base={'rooms':[],'modules':[],'events':[event]}
    with connection(server.DB) as db:db.execute('INSERT INTO config VALUES (1,?)',(json.dumps(base),))
    server.save_config({'rooms':[],'modules':[],'events':[]})
    self.assertEqual(server.get_config()['events'],[event])
    server.save_config({'rooms':[],'modules':[],'events':[{**event,'acknowledged':False}]})
    self.assertTrue(server.get_config()['events'][0]['acknowledged'])
    with connection(server.DB) as db:db.execute('UPDATE config SET value=? WHERE id=1',(json.dumps({'rooms':[],'modules':[],'events':[],'eventsClearedAt':123}),))
    server.save_config(base)
    self.assertEqual(server.get_config()['events'],[])
    self.assertEqual(server.get_config()['eventsClearedAt'],123)
   finally:server.DB=old

class CalendarTests(unittest.TestCase):
 def setUp(self):self.t={'id':'polycam-test','name':'Polycam','start':'2026-10-08','days':7,'status':'Active Trial','timezone':'Asia/Kolkata'}
 def test_final_dates_and_persistent_overdue_series(self):
  p=calendar_payloads(self.t);self.assertEqual([x['start']['dateTime'] for x in p],['2026-10-12T09:00:00','2026-10-13T09:00:00','2026-10-14T09:00:00','2026-10-15T09:00:00']);self.assertEqual(p[-1]['recurrence'],['RRULE:FREQ=DAILY']);self.assertEqual(len(set(x['id'] for x in p)),4)
 def test_retry_uses_deterministic_event_identity(self):
  client=GoogleCalendar('test-token');calls=[]
  def fake(path,method,body=None):
   calls.append((path,method,body))
   if method=='POST':raise RuntimeError('External API returned HTTP 409')
   return {'htmlLink':'example'}
  with patch.object(client,'call',side_effect=fake):self.assertEqual(len(client.sync(self.t)),4)
  self.assertEqual([x[1] for x in calls],['POST','PUT']*4)
 def test_verified_cancellation_clears_all_generated_events(self):
  self.t['status']='Cancelled & Verified';client=GoogleCalendar('test-token')
  with patch.object(client,'call',return_value={}) as request:
   client.sync(self.t);self.assertEqual(request.call_count,4);self.assertTrue(all(c.args[1]=='DELETE' for c in request.call_args_list))
 def test_missing_api_credentials_are_not_success(self):
  with patch.dict('os.environ',{},clear=True):
   with self.assertRaises(ValueError):Polycam().captures()
   with self.assertRaises(ValueError):GoogleCalendar().sync(self.t)


class AwayTests(unittest.TestCase):
 def test_live_rule_requires_fresh_verified_consecutive_motion(self):
  from rules import AwayRule
  rule=AwayRule();home={'away':True,'dataSource':'live','rooms':[{'id':'r','name':'Living'}],'modules':[{'id':'m','roomId':'r'}]}
  def state(i,v=70,verified=True):return {'connected':True,'radar_verified':verified,'last_frame':{'sequence':i,'received_at':100+i*.2,'reported_points':1,'points':[{'velocity_cm_s':v}]}}
  self.assertIsNone(rule.evaluate(home,state(1),100.2));self.assertIsNone(rule.evaluate(home,state(2),100.4))
  event=rule.evaluate(home,state(3),100.6);self.assertEqual(event['source'],'live');self.assertEqual(event['room'],'Living');home['events']=[event]
  self.assertEqual([sample['sequence'] for sample in event['samples']],[1,2,3])
  self.assertIsNone(rule.evaluate(home,state(4),100.8));self.assertIsNone(rule.evaluate(home,state(5),103))
  self.assertIsNone(rule.evaluate(home,state(6,verified=False),101.2))
 def test_sparse_motion_reports_raise_one_review_event(self):
  from rules import AwayRule
  rule=AwayRule();home={'away':True,'dataSource':'live','rooms':[{'id':'r','name':'Living'}],'modules':[{'id':'m','roomId':'r'}]}
  for i in range(1,8):
   moving=i in (1,4,7)
   frame={'sequence':i,'received_at':100+i,'reported_points':int(moving),'points':[{'velocity_cm_s':70}] if moving else []}
   event=rule.evaluate(home,{'connected':True,'radar_verified':True,'last_frame':frame},100+i)
   if i<7:self.assertIsNone(event)
  self.assertIsNotNone(event)
  self.assertEqual(event['room'],'Living')
  self.assertTrue(event['newEpisode'])
 def test_repeated_out_of_room_motion_creates_unverified_location_review(self):
  from rules import AwayRule
  room={'id':'r','name':'Classroom','boundary':[{'x':0,'z':0},{'x':2,'z':0},{'x':2,'z':2},{'x':0,'z':2}]}
  home={'away':True,'dataSource':'live','rooms':[room],'modules':[{'id':'m','roomId':'r','name':'Desk radar','x':1,'z':1,'yaw':0}]}
  rule=AwayRule()
  for i in range(1,10):
   moving=i in (1,3,5,7,9)
   frame={'sequence':i,'received_at':100+i*.7,'reported_points':int(moving),'points':[{'x_cm':400,'y_cm':400,'velocity_cm_s':-112}] if moving else []}
   event=rule.evaluate(home,{'connected':True,'radar_verified':True,'last_frame':frame},frame['received_at'])
   if i<9:self.assertIsNone(event)
  self.assertTrue(event['newEpisode'])
  self.assertTrue(event['locationUnverified'])
  self.assertIn('location unverified',event['room'])
 def test_replay_and_duplicate_frames_do_not_raise_live_events(self):
  from rules import AwayRule
  rule=AwayRule();home={'away':True,'dataSource':'recorded'};state={'connected':True,'radar_verified':True,'last_frame':{'sequence':1,'received_at':100,'reported_points':1,'points':[{'velocity_cm_s':70}]}}
  self.assertIsNone(rule.evaluate(home,state,100));home.update(dataSource='live',rooms=[],modules=[])
  for _ in range(10):self.assertIsNone(rule.evaluate(home,state,100))


class NodeTests(unittest.TestCase):
 def test_node_transport_state_is_independent(self):
  from nodes import NodeRegistry
  nodes=NodeRegistry();a=nodes.get('a');b=nodes.get('b')
  a.set_state(connected=True,version='A');b.set_state(connected=False,version='B')
  self.assertTrue(nodes.snapshot()['a']['connected']);self.assertFalse(nodes.snapshot()['b']['connected']);self.assertIsNot(a.STATE,b.STATE)
 def test_duplicate_port_claim_is_rejected(self):
  from nodes import NodeRegistry
  from unittest.mock import Mock
  nodes=NodeRegistry();a=nodes.get('a');a.WORKER=Mock();a.WORKER.is_alive.return_value=True;a.set_state(port='test-port')
  with self.assertRaisesRegex(ValueError,'another module'):nodes.connect('b','test-port')
 def test_each_live_event_keeps_its_module_and_room(self):
  from nodes import NodeRegistry
  nodes=NodeRegistry();home={'away':True,'dataSource':'live','rooms':[{'id':'ra','name':'Living'},{'id':'rb','name':'Bedroom'}],'modules':[{'id':'a','roomId':'ra'},{'id':'b','roomId':'rb'}]}
  for i in range(1,4):
   for key in ('a','b'):nodes.get(key).set_state(connected=True,radar_verified=True,last_frame={'sequence':i,'received_at':100+i*.2,'reported_points':1,'points':[{'velocity_cm_s':70}]})
   events=nodes.evaluate(home,100+i*.2)
  self.assertEqual({e['moduleId']:e['room'] for e in events},{'a':'Living','b':'Bedroom'})


class MultiNodeApiTests(unittest.TestCase):
 def test_http_state_exports_and_controls_keep_source_binding(self):
  import sqlite3,threading,urllib.request
  from http.server import ThreadingHTTPServer
  from nodes import NodeRegistry
  from unittest.mock import Mock
  with tempfile.TemporaryDirectory() as folder:
   old_auth=server.AUTH
   old_db,old_nodes=server.DB,server.NODES;server.DB=Path(folder)/'api.sqlite3';server.NODES=NodeRegistry()
   with connection(server.DB) as db:db.execute('CREATE TABLE config (id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
   from auth import Auth
   server.AUTH=Auth(server.DB)
   home={'rooms':[],'modules':[{'id':'a','roomId':'r'},{'id':'b','roomId':'r'}],'events':[],'activeModuleId':'a'}
   server.save_config(home)
   for node_id,value in [('a',1),('b',2)]:
    node=server.NODES.get(node_id);frame={'sequence':value,'received_at':100,'points':[],'reported_points':0}
    node.set_state(connected=True,radar_verified=True,last_frame=frame,frames=[frame],version='test-'+node_id)
    node.WORKER=Mock();node.WORKER.is_alive.return_value=True
   http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   def request(path,body=None):
    headers={'Host':'127.0.0.1:8768','Content-Type':'application/json'}
    req=urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    return json.load(urllib.request.urlopen(req))
   try:
    state=request('/api/state');self.assertEqual(set(state['nodes']),{'a','b'});self.assertEqual(state['last_frame']['sequence'],1)
    exported=request('/api/export?moduleId=b');self.assertEqual(exported['moduleId'],'b');self.assertEqual(exported['frames'][0]['sequence'],2)
    trial={'id':'trial-test','name':'Test','start':'2026-10-01','days':7,'status':'Active Trial'}
    home['trials']=[trial];server.save_config(home)
    with patch.object(server.GoogleTasks,'sync',return_value=[{'id':'test-task','state':'synced'}]):
     outcome=request('/api/tasks/sync',{'trialId':'trial-test'});self.assertEqual(outcome['sync']['state'],'synced')
    records=request('/api/state')['syncRecords'];self.assertEqual(records[0]['provider'],'tasks');self.assertEqual(records[0]['results'][0]['id'],'test-task')
    server.save_config(home);self.assertEqual(request('/api/state')['syncRecords'][0]['state'],'synced')
    server.NODES.get('b').set_state(stop_acknowledged=True,scan_running=False,scan_pending=False)
    annotated=request('/api/dataset/export',{'moduleId':'b','sessionId':'session-b','participantId':'participant-b','label':'empty-room'})
    self.assertEqual(annotated['module_id'],'b');self.assertEqual(annotated['frames'][0]['sequence'],2);self.assertFalse(annotated['annotation']['verified'])
    request('/api/stop',{'moduleId':'b'});server.NODES.get('b').WORKER.jobs.put.assert_called_once_with('stop');server.NODES.get('a').WORKER.jobs.put.assert_not_called()
   finally:
    http.shutdown();http.server_close();server.DB=old_db;server.NODES=old_nodes;server.AUTH=old_auth


class MonitoringTests(unittest.TestCase):
 def test_batched_wifi_reports_include_motion_before_latest_empty_frame(self):
  registry,node=self.make_node()
  home={'away':True,'dataSource':'live','rooms':[{'id':'r','name':'Room'}],'modules':[{'id':'a','roomId':'r'}],'events':[]}
  frames=[]
  for i in range(1,12):
   moving=i in (1,3,5,7,9)
   frames.append({'sequence':i,'received_at':100+i*.5,'reported_points':int(moving),'points':[{'velocity_cm_s':-100}] if moving else []})
  node.set_state(frames=frames,last_frame=frames[-1])
  # The last report is empty, but five earlier reports in this Wi-Fi batch moved.
  events=registry.evaluate(home,105.6)
  self.assertEqual(len([e for e in events if e['newEpisode']]),1)
  self.assertEqual(events[0]['room'],'Room')
  self.assertEqual(registry.evaluate({**home,'events':events[-1:]},105.7),[])
 def make_node(self):
  from nodes import NodeRegistry
  from unittest.mock import Mock
  registry=NodeRegistry();node=registry.get('a');node.WORKER=Mock();node.WORKER.is_alive.return_value=True;node.set_state(connected=True,radar_verified=True,version='V4.130.4.2')
  return registry,node
 def test_queues_one_cycle_and_repeats_only_after_completion(self):
  registry,node=self.make_node();registry.set_monitoring('a',True);registry.tick();registry.tick();node.WORKER.jobs.put.assert_called_once_with('scan')
  node.set_state(scan_pending=False,scan_running=True);registry.tick();self.assertEqual(node.WORKER.jobs.put.call_count,1)
  node.set_state(scan_running=False,stop_acknowledged=True);registry.tick();self.assertEqual(node.WORKER.jobs.put.call_count,2)
 def test_stop_disables_future_scans(self):
  registry,node=self.make_node();registry.set_monitoring('a',True);registry.tick();registry.control('a','stop');node.set_state(scan_pending=False,scan_running=False);registry.tick();self.assertFalse(registry.snapshot()['a']['monitoring']);self.assertEqual(node.WORKER.jobs.put.call_count,2)
 def test_fault_and_missing_stop_reply_disable_monitoring(self):
  for fault in [{'scan_error':'bad config'},{'stop_acknowledged':False},{'connected':False}]:
   registry,node=self.make_node();registry.set_monitoring('a',True);node.set_state(**fault);registry.tick();self.assertFalse(registry.snapshot()['a']['monitoring']);node.WORKER.jobs.put.assert_not_called()
 def test_unverified_or_wrong_firmware_cannot_start(self):
  registry,node=self.make_node();node.set_state(version='other')
  with self.assertRaises(ValueError):registry.set_monitoring('a',True)
  node.set_state(version='V4.130.4.2',radar_verified=False)
  with self.assertRaises(ValueError):registry.set_monitoring('a',True)


class AuthTests(unittest.TestCase):
 def test_hash_session_logout_and_restart(self):
  from auth import Auth
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'auth.sqlite3';auth=Auth(db);token=auth.setup('test-only-password-123');self.assertTrue(auth.authenticated('haven_session='+token))
   with connection(db) as c:row=c.execute('SELECT salt,digest FROM account').fetchone()
   self.assertNotIn('test-only-password-123',str(row));auth.logout('haven_session='+token);self.assertFalse(auth.authenticated('haven_session='+token))
   restarted=Auth(db);self.assertTrue(restarted.enrolled);self.assertFalse(restarted.authenticated('haven_session='+token));self.assertTrue(restarted.authenticated('haven_session='+restarted.login('test-only-password-123')))
 def test_failed_attempts_lock_and_expiry(self):
  from auth import Auth
  with tempfile.TemporaryDirectory() as folder:
   auth=Auth(Path(folder)/'auth.sqlite3');auth.setup('test-only-password-123')
   for _ in range(5):
    with self.assertRaisesRegex(ValueError,'Incorrect'):auth.login('wrong')
   with self.assertRaisesRegex(ValueError,'Wait 15'):auth.login('test-only-password-123')
   auth.failures=[];token=auth.login('test-only-password-123');auth.sessions[token]=0;self.assertFalse(auth.authenticated('haven_session='+token))


class AuthHttpTests(unittest.TestCase):
 def test_api_requires_cookie_and_logout_revokes_it(self):
  import sqlite3,threading,urllib.request,urllib.error
  from http.server import ThreadingHTTPServer
  from auth import Auth
  with tempfile.TemporaryDirectory() as folder:
   old_auth,old_db,old_models=server.AUTH,server.DB,server.MODELS
   from models import ModelStore
   server.MODELS=ModelStore(Path(folder)/"models");server.DB=Path(folder)/'auth-api.sqlite3'
   with connection(server.DB) as c:c.execute('CREATE TABLE config (id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
   server.AUTH=Auth(server.DB);http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
   def request(path,body=None,cookie=None,origin=None,host='127.0.0.1:8768'):
    headers={'Host':host,'Content-Type':'application/json'}
    if cookie:headers['Cookie']=cookie
    if origin:headers['Origin']=origin
    return urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+path,data=(body if isinstance(body,bytes) else json.dumps(body).encode()) if body is not None else None,headers=headers))
   try:
    response=request('/api/auth/setup',{'password':'test-only-password-123'});cookie=response.headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
    with self.assertRaises(urllib.error.HTTPError) as denied:request('/api/home')
    self.assertEqual(denied.exception.code,401);self.assertEqual(request('/api/home',cookie=cookie).status,200)
    with patch.dict('os.environ',{'HAVEN_ALLOWED_HOSTS':'haven.test:8768'}):
     config={'rooms':[],'modules':[],'events':[]}
     self.assertTrue(json.load(request('/api/home',config,cookie,'http://haven.test:8768','haven.test:8768'))['saved'])
     with self.assertRaises(urllib.error.HTTPError) as wrong_origin:request('/api/home',config,cookie,'https://other.test','haven.test:8768')
     self.assertEqual(wrong_origin.exception.code,403)
    from test_webpush import subscription
    with patch.dict('os.environ',{'HAVEN_VAPID_PRIVATE_KEY':'test-private','HAVEN_VAPID_PUBLIC_KEY':'test-public','HAVEN_VAPID_SUBJECT':'mailto:test@example.test'}):
     request('/api/push/subscribe',subscription(),cookie)
     self.assertEqual(json.load(request('/api/push/status',cookie=cookie))['devices'],1)
     with self.assertRaises(urllib.error.HTTPError) as push_denied:request('/api/push/status')
     self.assertEqual(push_denied.exception.code,401)
     request('/api/push/unsubscribe',{'endpoint':subscription()['endpoint']},cookie)
     self.assertEqual(json.load(request('/api/push/status',cookie=cookie))['devices'],0)
    import hashlib
    data=b'v 0 0 0\nv 1 0 0\nv 0 0 1\nf 1 2 3\n';model={'id':'http-scan','name':'Room.obj','created':'2026-10-09','scale':1,'files':[{'name':'Room.obj','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
    self.assertEqual(json.load(request('/api/models',model,cookie))['missing'],[0]);request('/api/models/http-scan/file/0',data,cookie)
    self.assertEqual(request('/api/models/http-scan/file/0',cookie=cookie).read(),data)
    with self.assertRaises(urllib.error.HTTPError) as model_denied:request('/api/models/http-scan/file/0')
    self.assertEqual(model_denied.exception.code,401)

    with self.assertRaises(urllib.error.HTTPError) as cross:request('/api/auth/logout',{},cookie,'https://example.com')
    self.assertEqual(cross.exception.code,403)
    for hostile_host in ('attacker.example:8768','127.0.0.1.attacker.example:8768'):
     with self.assertRaises(urllib.error.HTTPError) as rejected:request('/api/home',cookie=cookie,host=hostile_host)
     self.assertEqual(rejected.exception.code,403)
    for hostile_origin in ('http://attacker.example:8768','http://127.0.0.1.attacker.example:8768','https://127.0.0.1:8768'):
     with self.assertRaises(urllib.error.HTTPError) as rejected:request('/api/home',{'rooms':[],'modules':[],'events':[]},cookie,origin=hostile_origin)
     self.assertEqual(rejected.exception.code,403)
    request('/api/auth/logout',{},cookie)
    with self.assertRaises(urllib.error.HTTPError) as expired:request('/api/home',cookie=cookie)
    self.assertEqual(expired.exception.code,401)
   finally:http.shutdown();http.server_close();server.AUTH=old_auth;server.DB=old_db;server.MODELS=old_models


class ModelStoreTests(unittest.TestCase):
 def fixture(self,data=b'v 0 0 0\nv 1 0 0\nv 0 0 1\nf 1 2 3\n'):
  import hashlib
  return data,{'id':'scan-test','name':'Room.obj','created':'2026-10-09','scale':1,'files':[{'name':'Room.obj','size':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
 def test_upload_restart_retrieval_and_scale_update(self):
  from models import ModelStore
  import io
  with tempfile.TemporaryDirectory() as folder:
   store=ModelStore(folder);data,m=self.fixture();self.assertEqual(store.prepare(m),[0]);self.assertEqual(store.list(),[]);store.upload(m['id'],0,io.BytesIO(data),len(data));reopened=ModelStore(folder);file,name=reopened.file(m['id'],0);self.assertEqual(file.read_bytes(),data);self.assertEqual(name,'Room.obj');m['scale']=.01;self.assertEqual(reopened.prepare(m),[]);self.assertEqual(reopened.list()[0]['scale'],.01)
 def test_alignment_persists_and_invalid_settings_are_rejected(self):
  from models import ModelStore
  with tempfile.TemporaryDirectory() as folder:
   store=ModelStore(folder);data,m=self.fixture();m.update(upAxis='Z',yaw=90);store.prepare(m)
   self.assertEqual(store.manifest(m['id'])['upAxis'],'Z');self.assertEqual(store.manifest(m['id'])['yaw'],90)
   for changes in [{'upAxis':'X'},{'yaw':float('nan')},{'yaw':361}]:
    with self.assertRaises(ValueError):store.prepare({**m,**changes})
 def test_failed_integrity_never_publishes_partial_model(self):
  from models import ModelStore
  import io
  with tempfile.TemporaryDirectory() as folder:
   store=ModelStore(folder);data,m=self.fixture();store.prepare(m)
   with self.assertRaises(ValueError):store.upload(m['id'],0,io.BytesIO(b'x'*len(data)),len(data))
   self.assertEqual(store.list(),[]);self.assertFalse(list(Path(folder).glob('**/*.partial')))
   with self.assertRaises(ValueError):store.upload(m['id'],0,io.BytesIO(data[:-1]),len(data))
   with self.assertRaises(ValueError):store.file(m['id'],0)
 def test_replaced_manifest_hides_old_same_size_content(self):
  from models import ModelStore
  import io
  with tempfile.TemporaryDirectory() as folder:
   store=ModelStore(folder);data,m=self.fixture();store.prepare(m);store.upload(m['id'],0,io.BytesIO(data),len(data));new,newm=self.fixture(b'x'*len(data));self.assertEqual(store.prepare(newm),[0]);self.assertEqual(store.list(),[]);store.upload(m['id'],0,io.BytesIO(new),len(new));self.assertEqual(store.file(m['id'],0)[0].read_bytes(),new)
 def test_paths_unsupported_types_and_oversize_rejected(self):
  from models import ModelStore,MAX
  with tempfile.TemporaryDirectory() as folder:
   store=ModelStore(folder);data,m=self.fixture()
   with self.assertRaises(ValueError):store.folder('../private')
   for name in ['../Room.obj','page.html','Room.svg']:
    m['files'][0]['name']=name
    with self.assertRaises(ValueError):store.prepare(m)
   m['files'][0].update(name='Room.obj',size=MAX+1)
   with self.assertRaises(ValueError):store.prepare(m)

if __name__=='__main__':unittest.main()
