"""Optional official API adapters. Credentials come from environment, never the browser."""
import os,json,hashlib,time,urllib.request,urllib.error
from datetime import date,datetime,timedelta
from urllib.parse import quote

def request_json(url,method='GET',body=None,token=None,retry=True):
 data=json.dumps(body).encode() if body is not None else None
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 for attempt in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),timeout=15) as r:
    raw=r.read();return json.loads(raw) if raw else {}
  except urllib.error.HTTPError as e:
   if retry and e.code in (429,500,502,503,504) and attempt<2:time.sleep(2**attempt);continue
   raise RuntimeError(f'External API returned HTTP {e.code}; check account permissions and credentials') from None
  except urllib.error.URLError:
   raise RuntimeError('External API is unavailable; changes remain pending for retry') from None

def calendar_payloads(trial):
 start=date.fromisoformat(trial['start']);end=start+timedelta(days=int(trial['days']))
 zone=trial.get('timezone','Asia/Kolkata')
 rows=[]
 for offset in (3,2,1,0):
  d=end-timedelta(days=offset)
  identity=hashlib.sha256((trial['id']+'-'+str(offset)).encode()).hexdigest()
  payload={'id':identity,'summary':'HIGH PRIORITY: Cancel '+trial['name']+' trial','description':'Verify cancellation before renewal. This is a cancellation reminder, not automatic cancellation.','start':{'dateTime':d.isoformat()+'T09:00:00','timeZone':zone},'end':{'dateTime':d.isoformat()+'T09:15:00','timeZone':zone},'colorId':'11','reminders':{'useDefault':False,'overrides':[{'method':'popup','minutes':0},{'method':'popup','minutes':60}]},'extendedProperties':{'private':{'havenTrial':trial['id'],'urgency':'high'}}}
  if offset==0:payload['recurrence']=['RRULE:FREQ=DAILY']
  rows.append(payload)
 return rows

class GoogleCalendar:
 def __init__(self,token=None):self.token=token or os.getenv('GOOGLE_ACCESS_TOKEN');self.refresh=os.getenv('GOOGLE_REFRESH_TOKEN')
 @property
 def configured(self):return bool(self.token or (self.refresh and os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET')))
 def refresh_token(self):
  from urllib.parse import urlencode
  data=urlencode({'grant_type':'refresh_token','refresh_token':self.refresh,'client_id':os.getenv('GOOGLE_CLIENT_ID'),'client_secret':os.getenv('GOOGLE_CLIENT_SECRET')}).encode()
  try:
   with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token',data=data,headers={'Content-Type':'application/x-www-form-urlencoded'}),timeout=15) as r:self.token=json.load(r)['access_token']
  except Exception:raise RuntimeError('Google authorization needs reconnecting; calendar changes remain pending') from None
 def call(self,path,method='GET',body=None):
  if not self.configured:raise ValueError('Google Calendar is not authenticated. Configure server credentials first.')
  if not self.token:self.refresh_token()
  url='https://www.googleapis.com/calendar/v3/calendars/'+quote(os.getenv('GOOGLE_CALENDAR_ID','primary'),safe='')+'/events'+path
  try:return request_json(url,method,body,self.token)
  except RuntimeError as e:
   if 'HTTP 401' in str(e) and self.refresh:
    self.refresh_token();return request_json(url,method,body,self.token)
   raise
 def sync(self,trial):
  result=[]
  for payload in calendar_payloads(trial):
   if trial['status']=='Cancelled & Verified':
    try:self.call('/'+payload['id'],'DELETE')
    except RuntimeError as e:
     if not any(x in str(e) for x in ('HTTP 404','HTTP 410')):raise
    result.append({'id':payload['id'],'state':'removed'})
   else:
    try:value=self.call('','POST',payload)
    except RuntimeError as e:
     if 'HTTP 409' not in str(e):raise
     value=self.call('/'+payload['id'],'PUT',payload)
    result.append({'id':payload['id'],'state':'synced','url':value.get('htmlLink')})
  return result

class Polycam:
 @property
 def configured(self):return bool(os.getenv('POLYCAM_API_TOKEN'))
 def call(self,path):
  if not self.configured:raise ValueError('Polycam API is not configured. Enterprise API access and a server token are required; use a local export meanwhile.')
  return request_json('https://poly.cam/api/v1/'+path,token=os.getenv('POLYCAM_API_TOKEN'))
 def captures(self):return self.call('captures?limit=25')
 def artifacts(self,capture_id):
  if not capture_id or len(capture_id)>200:raise ValueError('Invalid capture id')
  return self.call('captures/'+quote(capture_id,safe='')+'/export')

# Tasks has date-only scheduling and no priority/recurrence API fields.
TASKS_SYNC_LOCK=__import__('threading').RLock()
def task_payloads(trial):
 end=date.fromisoformat(trial['start'])+timedelta(days=int(trial['days']))
 rows=[]
 for offset in (3,2,1,0):
  marker='haven-trial:'+hashlib.sha256((trial['id']+'-'+str(offset)).encode()).hexdigest()
  rows.append({'title':'HIGH PRIORITY: Cancel '+trial['name']+' trial','notes':marker+'\nConfirm cancellation with the provider and record the reference in Haven. This task does not cancel the subscription.','due':(end-timedelta(days=offset)).isoformat()+'T00:00:00Z','status':'completed' if trial['status']=='Cancelled & Verified' else 'needsAction'})
 return rows

class GoogleTasks(GoogleCalendar):
 def call(self,path,method='GET',body=None):
  if not self.configured:raise ValueError('Google Tasks is not authenticated. Configure server credentials and Tasks scope first.')
  if not self.token:self.refresh_token()
  url='https://tasks.googleapis.com/tasks/v1/lists/'+quote(os.getenv('GOOGLE_TASK_LIST_ID','@default'),safe='')+'/tasks'+path
  try:return request_json(url,method,body,self.token,retry=method!='POST')
  except RuntimeError as exc:
   if 'HTTP 401' in str(exc) and self.refresh:
    self.refresh_token();return request_json(url,method,body,self.token,retry=method!='POST')
   raise
 def sync(self,trial):
  with TASKS_SYNC_LOCK:
   found={};page=None;seen=set()
   while True:
    path='?showCompleted=true&showHidden=true&maxResults=100'+('&pageToken='+quote(page,safe='') if page else '')
    value=self.call(path)
    for task in value.get('items',[]):
     marker=task.get('notes','').split('\n')[0]
     if marker.startswith('haven-trial:') and task.get('id'):found.setdefault(marker,[]).append(task['id'])
    page=value.get('nextPageToken')
    if not page:break
    if page in seen:raise RuntimeError('Google Tasks returned repeated pagination; sync remains pending')
    seen.add(page)
   results=[]
   for payload in task_payloads(trial):
    marker=payload['notes'].split('\n')[0];ids=found.get(marker,[])
    if not ids and payload['status']=='completed':continue
    if ids:
     for task_id in ids:
      value=self.call('/'+quote(task_id,safe=''),'PATCH',payload)
      results.append({'id':value.get('id',task_id),'state':'completed' if payload['status']=='completed' else 'synced'})
    else:
     value=self.call('','POST',payload)
     if not value.get('id'):raise RuntimeError('Google Tasks did not confirm a task identifier; sync remains pending')
     results.append({'id':value['id'],'state':'synced'})
   return results
