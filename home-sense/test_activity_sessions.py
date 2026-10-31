"""Synthetic recordings only; no fixture is written to the real Haven database."""
import copy,hashlib,json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from activity_sessions import ActivitySessions,quality
from database import connection
from dataset import annotated_snapshot

def fixture():
 home={'rooms':[],'modules':[{'id':'fixture-module','roomId':'fixture-room','x':1,'z':2,'yaw':0}],'events':[]}
 frames=[{'sequence':i+1,'received_at':1000+i*.2,'reported_points':5,'preview_incomplete':True,
  'points':[{'x_cm':10+i,'y_cm':20,'z_cm':30,'velocity_cm_s':40}]} for i in range(16)]
 nodes={'fixture-module':{'radar_verified':True,'stop_acknowledged':True,'version':'fixture-only','frames':frames}}
 body={'moduleId':'fixture-module','sessionId':'fixture-session','participantId':'fixture-participant','label':'walking'}
 return home,nodes,body

def capture():return annotated_snapshot(*fixture())

class ActivitySessionTests(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.path=Path(self.folder.name)/'fixture.sqlite3';self.store=ActivitySessions(lambda:self.path)
 def test_delete_removes_capture_reviews_and_export(self):
  key=self.store.save(capture())['id']
  self.store.review(key,'reviewed','walking','Observed fixture',True)
  for confirm in (False,None,1):
   with self.assertRaises(ValueError):self.store.delete(key,confirm)
  self.assertEqual(len(self.store.bundle()['sessions']),1)
  self.store.delete(key,True)
  self.assertEqual(self.store.list(),[]);self.assertEqual(self.store.bundle()['sessions'],[])
  with connection(self.path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM activity_reviews').fetchone()[0],0)
  with self.assertRaises(ValueError):self.store.get(key)
  with self.assertRaises(ValueError):self.store.delete(key,True)
 def test_restart_and_immutable_capture_with_review_history(self):
  original=capture();saved=self.store.save(original);key=saved['id']
  self.assertEqual(saved['review']['state'],'pending');self.assertEqual(saved['quality']['duration_seconds'],3)
  self.assertEqual(saved['quality']['incomplete_reports'],16);self.assertEqual(self.store.bundle()['sessions'],[])
  reviewed=self.store.review(key,'reviewed','standing','Fixture correction from observed notes',True)
  self.assertEqual(reviewed['capture'],original);self.assertFalse(reviewed['capture']['annotation']['verified'])
  restarted=ActivitySessions(lambda:self.path);bundle=restarted.bundle()
  self.assertEqual(bundle['sessions'][0]['review']['label'],'standing');self.assertFalse(bundle['live_classifier_enabled'])
  self.assertEqual(bundle['sessions'][0]['capture']['annotation']['label'],'walking')
  restarted.review(key,'excluded','standing','Fixture interrupted trial',False)
  self.assertEqual(len(restarted.get(key)['review_history']),2);self.assertEqual(restarted.bundle()['sessions'],[])
  restarted.review(key,'pending','unlabelled','Fixture needs checking',False)
  self.assertEqual(len(restarted.get(key)['review_history']),3)
 def test_review_requires_real_operator_confirmation_and_notes(self):
  key=self.store.save(capture())['id']
  for state,label,notes,confirmed in [('reviewed','walking','',True),('reviewed','walking','note',False),('reviewed','unlabelled','note',True),('reviewed','walking','note',1),('verified','walking','note',True),('pending',[],None,False)]:
   with self.assertRaises(ValueError):self.store.review(key,state,label,notes,confirmed)
  self.assertEqual(self.store.get(key)['review_history'],[])
 def test_duplicate_capture_and_identifiers_cannot_create_split_leakage(self):
  v=capture();self.store.save(v)
  v['participant_id']='other-fixture-person';v['session_id']='other-fixture-session'
  with self.assertRaisesRegex(ValueError,'already saved'):self.store.save(v)
  v=capture();v['frames'][0]['points'][0]['x_cm']=999
  source={'source':v['source'],'moduleId':v['module_id'],'version':v['firmware'],'frames':v['frames']}
  v['source_sha256']=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
  v['participant_id']=' fixture-participant ';v['session_id']=' fixture-session '
  with self.assertRaisesRegex(ValueError,'already saved'):self.store.save(v)
  self.assertEqual(len(self.store.list()),1)
 def test_tampered_snapshot_or_stored_payload_refused(self):
  v=capture();v['frames'][0]['points'][0]['x_cm']=999
  with self.assertRaisesRegex(ValueError,'snapshot integrity'):self.store.save(v)
  key=self.store.save(capture())['id']
  with connection(self.path) as db:db.execute('UPDATE activity_sessions SET payload=? WHERE id=?',('{}',key))
  with self.assertRaisesRegex(ValueError,'integrity'):self.store.get(key)
  with self.assertRaises(ValueError):self.store.bundle()
 def test_invalid_report_shapes_counts_and_coordinates(self):
  mutations=[lambda v:v.update(annotation=[]),lambda v:v['annotation'].update(verified=True),lambda v:v.update(complete_binary_cloud=True),
   lambda v:v.update(source='recorded'),lambda v:v.update(frames=[]),lambda v:v['frames'][0].update(sequence=True),
   lambda v:v['frames'][0].update(sequence=1.5),lambda v:v['frames'][1].update(sequence=1),
   lambda v:v['frames'][0].update(reported_points=0),lambda v:v['frames'][0].update(reported_points=True),
   lambda v:v['frames'][0]['points'][0].update(x_cm=float('nan')),lambda v:v['frames'][0]['points'][0].update(velocity_cm_s=True)]
  for mutate in mutations:
   v=capture();mutate(v)
   with self.assertRaises(ValueError):quality(v)
  with self.assertRaises(ValueError):quality([])
 def test_missing_unordered_short_times_stay_draft_and_empty_room_can_export(self):
  for mutation in [lambda f:f[0].pop('received_at'),lambda f:f[1].update(received_at=999),lambda f:f.__delitem__(slice(5,None))]:
   home,nodes,body=fixture();mutation(nodes['fixture-module']['frames']);body['sessionId']='draft-'+str(len(self.store.list()))
   key=self.store.save(annotated_snapshot(home,nodes,body))['id'];self.store.review(key,'reviewed','walking','Fixture observations',True)
   self.assertFalse(next(s for s in self.store.list() if s['id']==key)['training_eligible'])
  home,nodes,body=fixture()
  for f in nodes['fixture-module']['frames']:f.update(points=[],reported_points=0,preview_incomplete=False)
  body.update(label='empty-room',sessionId='fixture-empty',participantId='fixture-empty-person')
  key=self.store.save(annotated_snapshot(home,nodes,body))['id'];self.store.review(key,'reviewed','empty-room','Fixture room empty throughout',True)
  bundle=self.store.bundle();self.assertEqual(len(bundle['sessions']),1);self.assertEqual(bundle['excluded_session_count'],3)
  self.assertEqual(bundle['sessions'][0]['quality']['zero_point_reports'],16)

class ActivityApiTests(unittest.TestCase):
 def test_authenticated_live_save_review_export_and_guards(self):
  import server
  from auth import Auth
  from nodes import NodeRegistry
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'fixture.sqlite3';auth=Auth(path);cookie='haven_session='+auth.setup('fixture-only-password-123')
   nodes=NodeRegistry();home,snapshots,body=fixture();node=nodes.get('fixture-module');node.set_state(**snapshots['fixture-module'])
   store=ActivitySessions(lambda:path)
   with patch.multiple(server,DB=path,AUTH=auth,NODES=nodes,ACTIVITY_SESSIONS=store):
    with connection(path) as db:db.execute('CREATE TABLE config (id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
    server.save_config(home)
    http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    def request(route,body=None,cookie_value=cookie,origin=None):
     headers={'Host':'127.0.0.1:8768','Content-Type':'application/json','Cookie':cookie_value}
     if origin:headers['Origin']=origin
     req=urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+route,data=json.dumps(body).encode() if body is not None else None,headers=headers)
     with urllib.request.urlopen(req) as response:return json.load(response)
    try:
     for route,payload in [('/api/dataset/sessions',None),('/api/dataset/training-export',None),('/api/dataset/save',body),('/api/dataset/review',{}),('/api/dataset/delete',{'id':'fixture','confirm':True})]:
      with self.assertRaises(urllib.error.HTTPError) as exc:request(route,payload,cookie_value='')
      self.assertEqual(exc.exception.code,401)
     with self.assertRaises(urllib.error.HTTPError) as exc:request('/api/dataset/save',body,origin='http://elsewhere.test')
     self.assertEqual(exc.exception.code,403)
     for state in [{'scan_running':True},{'scan_pending':True},{'stop_acknowledged':False},{'radar_verified':False},{'scan_error':'fault'}]:
      node.set_state(**snapshots['fixture-module'],scan_running=False,scan_pending=False,scan_error=None);node.set_state(**state)
      with self.assertRaises(urllib.error.HTTPError) as exc:request('/api/dataset/save',body)
      self.assertEqual(exc.exception.code,400)
     node.set_state(**snapshots['fixture-module'],scan_running=False,scan_pending=False,scan_error=None)
     nodes.monitoring['fixture-module']=True
     with self.assertRaises(urllib.error.HTTPError):request('/api/dataset/save',body)
     nodes.monitoring['fixture-module']=False
     # The API takes readings from the selected live node, ignoring client-supplied fake frames.
     result=request('/api/dataset/save',{**body,'frames':[{'fabricated':True}]});key=result['id']
     self.assertEqual(result['capture']['frames'],snapshots['fixture-module']['frames'])
     self.assertEqual(request('/api/dataset/training-export')['sessions'],[])
     request('/api/dataset/review',{'id':key,'state':'reviewed','label':'walking','notes':'Synthetic fixture observed throughout','confirmObserved':True})
     self.assertTrue(request('/api/dataset/sessions')[0]['training_eligible'])
     self.assertEqual(request('/api/dataset/sessions/'+key)['capture'],result['capture'])
     self.assertEqual(request('/api/dataset/training-export')['sessions'][0]['id'],key)
     with self.assertRaises(urllib.error.HTTPError):request('/api/dataset/save',body)
     with self.assertRaises(urllib.error.HTTPError):request('/api/dataset/save',[])
     with connection(path) as db:db.execute('UPDATE activity_sessions SET payload=? WHERE id=?',('{}',key))
     for route in ('/api/dataset/sessions','/api/dataset/training-export','/api/dataset/sessions/'+key):
      with self.assertRaises(urllib.error.HTTPError) as exc:request(route)
      self.assertEqual(exc.exception.code,400)
    finally:http.shutdown();http.server_close();thread.join()
