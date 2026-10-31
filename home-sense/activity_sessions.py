"""Durable operator-annotated radar sessions; observations remain immutable."""
import hashlib,json,math,sqlite3,uuid
from datetime import datetime,timezone
from database import connection
from dataset import LABELS
from csi_recordings import quality as csi_quality

def now():return datetime.now(timezone.utc).isoformat()
def text(value,name,limit=100):
 if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError(name+' is required and must fit the size limit')
 return value.strip()
def encoded(value):return json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':'))

def quality(value):
 if not isinstance(value,dict):raise ValueError('Expected an annotated session')
 if value.get('schema')!='haven-annotated-preview-v1' or value.get('source')!='live ESP console preview':raise ValueError('Use an annotated live radar session')
 annotation=value.get('annotation')
 if not isinstance(annotation,dict) or not isinstance(annotation.get('label'),str) or annotation['label'] not in LABELS:raise ValueError('Unsupported activity label')
 if annotation.get('verified') is not False or value.get('complete_binary_cloud') is not False:raise ValueError('Console previews and operator labels must retain their unverified provenance')
 for field in ('session_id','participant_id','room_id','module_id'):text(value.get(field),field)
 frames=value.get('frames')
 if not isinstance(frames,list) or not 1<=len(frames)<=1000:raise ValueError('Session must contain 1–1000 reports')
 visible=reported=incomplete=zero=0;times=[];sequences=set()
 for frame in frames:
  if not isinstance(frame,dict):raise ValueError('Invalid report')
  seq=frame.get('sequence');count=frame.get('reported_points');points=frame.get('points')
  if type(seq) is not int or seq<0 or seq in sequences:raise ValueError('Report sequences must be unique nonnegative integers')
  sequences.add(seq)
  if type(count) is not int or count<0 or not isinstance(points,list) or len(points)>count:raise ValueError('Invalid report point counts')
  for point in points:
   if not isinstance(point,dict) or any(type(point.get(k)) not in (int,float) or not math.isfinite(point[k]) for k in ('x_cm','y_cm','z_cm','velocity_cm_s')):raise ValueError('Coordinates and velocity must be finite')
  stamp=frame.get('received_at')
  if type(stamp) in (int,float) and math.isfinite(stamp):times.append(stamp)
  visible+=len(points);reported+=count;incomplete+=count>len(points);zero+=count==0
 ordered=len(times)==len(frames) and all(a<b for a,b in zip(times,times[1:]))
 gaps=[b-a for a,b in zip(times,times[1:])] if ordered else []
 return {'csi':csi_quality(value),'reports':len(frames),'visible_points':visible,'reported_points':reported,'incomplete_reports':incomplete,
  'zero_point_reports':zero,'fully_timestamped':len(times)==len(frames),'time_ordered':ordered,
  'duration_seconds':times[-1]-times[0] if ordered else None,'max_gap_seconds':max(gaps) if gaps else None}

class ActivitySessions:
 def __init__(self,db):self.db=db
 def prepare(self,db):
  db.execute('CREATE TABLE IF NOT EXISTS activity_sessions (id TEXT PRIMARY KEY, participant TEXT NOT NULL, session TEXT NOT NULL, source_hash TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, payload_hash TEXT NOT NULL, created TEXT NOT NULL, UNIQUE(participant,session))')
  db.execute('CREATE TABLE IF NOT EXISTS activity_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, payload TEXT NOT NULL, created TEXT NOT NULL)')
 def save(self,value):
  quality(value)
  value={**value,**{k:text(value[k],k) for k in ('session_id','participant_id','room_id','module_id')}}
  source=text(value.get('source_sha256'),'Source hash',64)
  if len(source)!=64 or any(c not in '0123456789abcdef' for c in source):raise ValueError('Invalid source hash')
  # Check the exact canonical snapshot hash produced by the acquisition service.
  capture={'source':value['source'],'moduleId':value['module_id'],'version':value.get('firmware'),'frames':value['frames']}
  expected=hashlib.sha256(json.dumps(capture,sort_keys=True,allow_nan=False).encode()).hexdigest()
  if source!=expected:raise ValueError('Source snapshot integrity check failed')
  payload=encoded(value)
  if len(payload.encode())>1024*1024:raise ValueError('Session exceeds 1 MB')
  key=str(uuid.uuid4());created=now()
  try:
   with connection(self.db()) as db:
    self.prepare(db);db.execute('BEGIN IMMEDIATE')
    if db.execute('SELECT COUNT(*) FROM activity_sessions').fetchone()[0]>=500:raise ValueError('Session storage limit reached')
    db.execute('INSERT INTO activity_sessions VALUES (?,?,?,?,?,?,?)',(key,value['participant_id'],value['session_id'],source,payload,hashlib.sha256(payload.encode()).hexdigest(),created))
  except sqlite3.IntegrityError as exc:raise ValueError('This capture or participant/session identifier is already saved; review the existing session') from exc
  return self.get(key)
 def _get(self,db,key):
  row=db.execute('SELECT payload,payload_hash,created FROM activity_sessions WHERE id=?',(key,)).fetchone()
  if not row:raise ValueError('Saved session not found')
  if hashlib.sha256(row[0].encode()).hexdigest()!=row[1]:raise ValueError('Saved session integrity check failed')
  value=json.loads(row[0]);history=[{'review':json.loads(r[0]),'at':r[1]} for r in db.execute('SELECT payload,created FROM activity_reviews WHERE session_id=? ORDER BY id',(key,))]
  review=history[-1] if history else None
  return {'id':key,'created_at':row[2],'capture':value,'quality':quality(value),
   'review':review['review'] if review else {'state':'pending','label':value['annotation']['label']},
   'reviewed_at':review['at'] if review else None,'review_history':history}
 def get(self,key):
  with connection(self.db()) as db:self.prepare(db);return self._get(db,key)
 def summary(self,value):
  cap=value['capture'];review=value['review'];q=value['quality']
  eligible=review['state']=='reviewed' and review['label']!='unlabelled' and cap.get('room_assignment_verified') is True and q['time_ordered'] and q['duration_seconds'] is not None and q['duration_seconds']>=2
  return {k:value[k] for k in ('id','created_at','reviewed_at','quality')}|{'session_id':cap['session_id'],'participant_id':cap['participant_id'],'module_id':cap['module_id'],'room_id':cap['room_id'],'room_assignment_verified':cap.get('room_assignment_verified') is True,
   'label':review['label'],'review_state':review['state'],'training_eligible':eligible,'paired_training_candidate':bool(eligible and q['csi']['paired'])}
 def list(self):
  with connection(self.db()) as db:
   self.prepare(db);keys=[r[0] for r in db.execute('SELECT id FROM activity_sessions ORDER BY created DESC,id')]
   return [self.summary(self._get(db,key)) for key in keys]
 def review(self,key,state,label,notes,confirmed):
  text(key,'Saved session')
  if not isinstance(state,str) or state not in ('pending','reviewed','excluded'):raise ValueError('Invalid review state')
  if not isinstance(label,str) or label not in LABELS:raise ValueError('Unsupported label')
  if not isinstance(notes,str) or len(notes)>1000:raise ValueError('Review notes must fit 1000 characters')
  if state=='reviewed' and (label=='unlabelled' or confirmed is not True or not notes.strip()):raise ValueError('Confirm you observed the activity throughout this recording and add review notes')
  review={'state':state,'label':label,'notes':notes.strip(),'confirmed_observed':confirmed is True,
   'basis':'Operator review of whole-session activity; not a model prediction or independent verification'}
  with connection(self.db()) as db:
   self.prepare(db);db.execute('BEGIN IMMEDIATE');self._get(db,key)
   db.execute('INSERT INTO activity_reviews (session_id,payload,created) VALUES (?,?,?)',(key,encoded(review),now()))
  return self.get(key)
 def delete(self,key,confirmed):
  text(key,'Saved session')
  if confirmed is not True:raise ValueError('Confirm deletion of this recording')
  with connection(self.db()) as db:
   self.prepare(db);db.execute('BEGIN IMMEDIATE')
   if not db.execute('SELECT 1 FROM activity_sessions WHERE id=?',(key,)).fetchone():raise ValueError('Saved session not found')
   db.execute('DELETE FROM activity_reviews WHERE session_id=?',(key,))
   db.execute('DELETE FROM activity_sessions WHERE id=?',(key,))
  return {'deleted':True,'id':key}
 def bundle(self):
  with connection(self.db()) as db:
   self.prepare(db);keys=[r[0] for r in db.execute('SELECT id FROM activity_sessions ORDER BY created,id')]
   values=[self._get(db,key) for key in keys]
  included=[v for v in values if self.summary(v)['training_eligible']]
  return {'schema':'haven-reviewed-preview-bundle-v1','created_at':now(),'target_domain':'RD-60 console previews',
   'label_basis':'Explicit operator reviews; no independently verified detections','sessions':included,
   'split_policy':'Keep each participant and original capture together across train/validation/test',
   'excluded_session_count':len(values)-len(included),'live_classifier_enabled':False}
