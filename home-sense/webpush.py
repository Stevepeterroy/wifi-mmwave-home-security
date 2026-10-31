"""Optional encrypted browser push; service acceptance is not device delivery."""
import sqlite3,json,hashlib,time,os,base64
from contextlib import contextmanager
from urllib.parse import urlparse

def validate_subscription(value):
 if not isinstance(value,dict):raise ValueError('Invalid push subscription')
 endpoint=value.get('endpoint');keys=value.get('keys')
 if not isinstance(endpoint,str) or len(endpoint)>2048:raise ValueError('Invalid push endpoint')
 url=urlparse(endpoint);host=url.hostname or ''
 allowed=host in ('fcm.googleapis.com','updates.push.services.mozilla.com','web.push.apple.com') or host.endswith('.notify.windows.com')
 if url.scheme!='https' or not allowed or url.username or url.password or url.port not in (None,443) or url.fragment:raise ValueError('Unsupported push provider endpoint')
 if not isinstance(keys,dict):raise ValueError('Push encryption keys are missing')
 for name,size in [('auth',16),('p256dh',65)]:
  key=keys.get(name)
  if not isinstance(key,str) or len(key)>200:raise ValueError('Invalid push encryption key')
  try:raw=base64.b64decode(key+'='*(-len(key)%4),altchars=b'-_',validate=True)
  except Exception:raise ValueError('Invalid push encryption key') from None
  if len(raw)!=size or (name=='p256dh' and raw[0]!=4):raise ValueError('Invalid push encryption key')
 return {'endpoint':endpoint,'keys':{k:keys[k] for k in ('auth','p256dh')}}

class PushStore:
 def __init__(self,path):self.path=path
 @contextmanager
 def connection(self):
  db=sqlite3.connect(self.path() if callable(self.path) else self.path)
  db.execute('CREATE TABLE IF NOT EXISTS push_subscriptions (id TEXT PRIMARY KEY,value TEXT NOT NULL)')
  db.execute('CREATE TABLE IF NOT EXISTS push_delivery (message TEXT,device TEXT,payload TEXT,state TEXT,attempts INTEGER,next REAL,error TEXT,PRIMARY KEY(message,device))')
  columns={row[1] for row in db.execute('PRAGMA table_info(push_delivery)')}
  for name in ('created','expires'):
   if name not in columns:db.execute('ALTER TABLE push_delivery ADD COLUMN '+name+' REAL NOT NULL DEFAULT 0')
  try:
   with db:yield db
  finally:db.close()
 def subscribe(self,value):
  value=validate_subscription(value);key=hashlib.sha256(value['endpoint'].encode()).hexdigest()
  with self.connection() as db:
   if db.execute('SELECT COUNT(*) FROM push_subscriptions').fetchone()[0]>=100 and not db.execute('SELECT 1 FROM push_subscriptions WHERE id=?',(key,)).fetchone():raise ValueError('Push device limit reached')
   db.execute('INSERT OR REPLACE INTO push_subscriptions VALUES (?,?)',(key,json.dumps(value)))
  return key
 def unsubscribe(self,endpoint):
  key=hashlib.sha256(endpoint.encode()).hexdigest()
  with self.connection() as db:db.execute('DELETE FROM push_subscriptions WHERE id=?',(key,));db.execute('DELETE FROM push_delivery WHERE device=?',(key,))
 def queue(self,message,payload,now=None,ttl=300):
  now=time.time() if now is None else now
  if not isinstance(ttl,(int,float)) or not 1<=ttl<=3600:raise ValueError('Invalid message lifetime')
  if not isinstance(message,str) or not isinstance(payload,dict) or len(json.dumps(payload))>3000:raise ValueError('Invalid push message')
  with self.connection() as db:
   for (key,) in db.execute('SELECT id FROM push_subscriptions').fetchall():db.execute('INSERT OR IGNORE INTO push_delivery (message,device,payload,state,attempts,next,error,created,expires) VALUES (?,?,?,\'pending\',0,0,NULL,?,?)',(message,key,json.dumps(payload),now,now+ttl))
 def cancel_inactive_trials(self,active):
  with self.connection() as db:
   for (message,) in db.execute("SELECT DISTINCT message FROM push_delivery WHERE state='pending' AND substr(message,1,6)='trial:'").fetchall():
    if not any(message.startswith('trial:'+identity+':') for identity in active):db.execute("UPDATE push_delivery SET state='cancelled',error=NULL WHERE message=?",(message,))
 def summary(self):
  with self.connection() as db:return {'devices':db.execute('SELECT COUNT(*) FROM push_subscriptions').fetchone()[0],'states':dict(db.execute('SELECT state,COUNT(*) FROM push_delivery GROUP BY state'))}
 def deliver(self,sender,now=None):
  now=time.time() if now is None else now
  with self.connection() as db:
   db.execute("UPDATE push_delivery SET state='expired',error='Message exceeded its useful lifetime' WHERE state='pending' AND expires<=?",(now,))
   rows=db.execute('SELECT d.message,d.device,d.payload,d.attempts,s.value FROM push_delivery d JOIN push_subscriptions s ON s.id=d.device WHERE d.state=\'pending\' AND d.next<=? LIMIT 20',(now,)).fetchall()
  for message,key,payload,attempts,subscription in rows:
   with self.connection() as db:
    if not db.execute("SELECT 1 FROM push_delivery d JOIN push_subscriptions s ON d.device=s.id WHERE d.message=? AND d.device=? AND d.state='pending' AND d.expires>?",(message,key,now)).fetchone():continue
   code=0
   try:code=sender(json.loads(subscription),json.loads(payload))
   except Exception:pass # Never retain endpoints, credentials or raw provider errors in status.
   if code in (404,410):
    with self.connection() as db:db.execute('DELETE FROM push_subscriptions WHERE id=?',(key,));db.execute("UPDATE push_delivery SET state='expired',error='Subscription expired' WHERE device=?",(key,))
    continue
   accepted=200<=code<300;terminal=not accepted and attempts>=4
   state='accepted_by_push_service' if accepted else 'failed' if terminal else 'pending'
   error=None if accepted else 'Push service did not accept the message; check configuration or retry'
   with self.connection() as db:db.execute('UPDATE push_delivery SET state=?,attempts=?,next=?,error=? WHERE message=? AND device=?',(state,attempts+1,now+min(3600,30*2**attempts),error,message,key))

class WebPush:
 @property
 def configured(self):return bool(os.getenv('HAVEN_VAPID_PRIVATE_KEY') and os.getenv('HAVEN_VAPID_PUBLIC_KEY') and os.getenv('HAVEN_VAPID_SUBJECT'))
 def send(self,subscription,payload):
  if not self.configured:raise ValueError('Web Push keys and contact subject are not configured')
  from pywebpush import webpush,WebPushException
  try:
   response=webpush(subscription_info=validate_subscription(subscription),data=json.dumps(payload),vapid_private_key=os.environ['HAVEN_VAPID_PRIVATE_KEY'],vapid_claims={'sub':os.environ['HAVEN_VAPID_SUBJECT']},ttl=300,timeout=10,headers={'Urgency':'high'})
   return response.status_code
  except WebPushException as exc:return exc.response.status_code if exc.response is not None else 0
