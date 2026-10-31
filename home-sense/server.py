from room_geometry import validate_boundary
"""Haven local service. Reuses the verified UART diagnostic protocol, explicit local ESP setup jobs support backed-up firmware installation."""
from database import connection
import sys,json,sqlite3,threading,time,os,math
from datetime import datetime
from pathlib import Path
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parent
if str(ROOT.parent/'radar-demo') not in sys.path:sys.path.append(str(ROOT.parent/'radar-demo'))
import importlib.util
transport_spec=importlib.util.spec_from_file_location('haven_radar_transport',ROOT.parent/'radar-demo'/'server.py')
radar=importlib.util.module_from_spec(transport_spec)
transport_spec.loader.exec_module(radar)
from integrations import GoogleCalendar,GoogleTasks,Polycam
from rules import AwayRule
from nodes import NodeRegistry
NODES=NodeRegistry()
from esp_setup import EspSetup
ESP_SETUP=EspSetup(ROOT,radar.ports)
DB=ROOT/'data'/'haven.sqlite3'; DB.parent.mkdir(exist_ok=True);DB.parent.chmod(0o700)
with connection(DB) as db:
 db.execute('CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
DB.chmod(0o600)
from auth import Auth
AUTH=Auth(DB)
from syncstate import SyncStore
SYNC=SyncStore(lambda:DB)
from webpush import PushStore,WebPush
PUSH=PushStore(lambda:DB)
from pushschedule import PushScheduler
SCHEDULER=PushScheduler(PUSH)
from models import ModelStore
MODELS=ModelStore(DB.parent/"models")
from wifi_transport import DeviceKeys,WifiBridge
DEVICE_KEYS=DeviceKeys(lambda:DB)
WIFI=WifiBridge()
from wifi_inventory import inventory
from wifi_discovery import DeviceDiscovery
DISCOVERY=DeviceDiscovery()
from csi_stream import CsiStreams
from motion_fusion import motion_evidence
from paired_captures import PairedCaptures
from activity_runtime import ActivityRuntime
ACTIVITY_RUNTIME=ActivityRuntime(os.getenv('HAVEN_ACTIVITY_MODEL'))
PAIRED_CAPTURES=PairedCaptures()
CSI=CsiStreams()
from radar_bytes import RadarBytes
RADAR_BYTES=RadarBytes()
from activity_sessions import ActivitySessions
ACTIVITY_SESSIONS=ActivitySessions(lambda:DB)
from email_alerts import EmailAlerts
EMAIL=EmailAlerts(DB.parent/"email-settings.json")
BIND=os.getenv("HAVEN_BIND","127.0.0.1")
TLS=bool(os.getenv("HAVEN_TLS_CERT") and os.getenv("HAVEN_TLS_KEY"))

def get_config():
 with connection(DB) as db:
  row=db.execute('SELECT value FROM config WHERE id=1').fetchone()
 return json.loads(row[0]) if row else None

def without_deleted_scans(home):
 deleted=set(MODELS.deleted_ids())
 removed_rooms={r['id'] for r in home.get('rooms',[]) if r.get('planModelId',r.get('modelId')) in deleted and 'id' in r}
 return {**home,
  'rooms':[r for r in home.get('rooms',[]) if r.get('planModelId',r.get('modelId')) not in deleted],
  **({'routers':[r for r in home.get('routers',[]) if r.get('planModelId',r.get('modelId')) not in deleted]} if 'routers' in home else {}),
  'modules':[{**m,'roomId':'','planModelId':None,'scanAlignment':None} if m.get('planModelId') in deleted or m.get('roomId') in removed_rooms else m for m in home.get('modules',[])]}

def save_config(v):
 if not isinstance(v,dict) or not isinstance(v.get('rooms'),list) or not isinstance(v.get('modules'),list):raise ValueError('Invalid home configuration')
 if len(v['rooms'])>100 or len(v['modules'])>100 or len(v.get('events',[]))>500:raise ValueError('Home configuration limit exceeded')
 v=without_deleted_scans(v)
 for r in v['rooms']:
  if any(not isinstance(r.get(k),(int,float)) or not math.isfinite(r[k]) for k in ('x','z','width','depth')) or not 0<r['width']<=100 or not 0<r['depth']<=100:raise ValueError('Room dimensions must be between 0 and 100 metres')
  validate_boundary(r)
 with connection(DB) as db:
  db.execute('BEGIN IMMEDIATE')
  row=db.execute('SELECT value FROM config WHERE id=1').fetchone()
  stored=json.loads(row[0]) if row else {}
  removed={m.get('id') for m in stored.get('modules',[]) if isinstance(m,dict)}-{m.get('id') for m in v['modules'] if isinstance(m,dict)}
  if removed:
   tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('device_keys','device_bindings')")}
   for table in tables:
    if any(db.execute(f'SELECT 1 FROM {table} WHERE module=?',(module,)).fetchone() for module in removed):
     raise ValueError('Forget the ESP pairing before deleting its sensor; refresh the page if this removal was unexpected')
  existing=stored.get('events',[])
  if 'eventsClearedAt' in stored:v={**v,'eventsClearedAt':stored['eventsClearedAt']}
  else:v.pop('eventsClearedAt',None)
  events={e['id']:e for e in existing}
  for event in v.get('events',[]):
   if event['id'] in events:events[event['id']]={**events[event['id']],'acknowledged':event.get('acknowledged',False) or events[event['id']].get('acknowledged',False)}
  v={**v,'events':sorted(events.values(),key=lambda e:e['at'],reverse=True)[:200]}
  db.execute('INSERT OR REPLACE INTO config VALUES (1,?)',(json.dumps(v,allow_nan=False),))

def monitor():
 while True:
  try:
   home=get_config()
   NODES.tick()
   events=NODES.evaluate(home)
   if events:
    with connection(DB) as db:
     db.execute('BEGIN IMMEDIATE')
     current=json.loads(db.execute('SELECT value FROM config WHERE id=1').fetchone()[0])
     if True:
      merged={e['id']:e for e in current.get('events',[])}
      for event in events:
       if datetime.fromisoformat(event['at']).timestamp()<=current.get('eventsClearedAt',0):continue
       if event.get('newEpisode') and event.get('modelId'):
        try:event['scanSnapshot']=MODELS.manifest(event['modelId'])
        except ValueError:pass
       merged[event['id']]={**event,'acknowledged':event.get('acknowledged',False) or merged.get(event['id'],{}).get('acknowledged',False)}
      current['events']=sorted(merged.values(),key=lambda e:e['at'],reverse=True)[:200]
      db.execute('UPDATE config SET value=? WHERE id=1',(json.dumps(current),))
    if current.get('away') and current.get('dataSource')=='live':
     for event in events:
      if event.get('newEpisode'):EMAIL.enqueue(event)
     for event in [e for e in events if e.get('newEpisode')]:PUSH.queue('away:'+event['id'],{'title':'Haven: motion to review','body':event['room']+': moving radar reflections at '+event['at']+'. Person identity is unverified.','tag':'away-'+event['id']})
  except Exception as exc:print('Live rule paused:',type(exc).__name__,flush=True)
  time.sleep(.1)

def push_monitor():
 while True:
  try:
   if WebPush().configured and AUTH.enrolled:
    # Trial safeguards were removed at the user’s request. Cancel queued trial alerts.
    SCHEDULER.tick({"trials": []})
    PUSH.deliver(WebPush().send)
  except Exception as exc:print('Push delivery paused:',type(exc).__name__,flush=True)
  time.sleep(5)

class Handler(radar.Handler):
 def origin_allowed(self):
  origin=self.headers.get('Origin')
  if not origin:return True
  from urllib.parse import urlparse
  parsed=urlparse(origin)
  import ssl
  scheme='https' if isinstance(self.connection,ssl.SSLSocket) else 'http'
  return parsed.scheme==scheme and parsed.netloc==self.headers.get('Host','') and not parsed.path and not parsed.params and not parsed.query and not parsed.fragment
 def valid_host(self):
  host=self.headers.get('Host','')
  allowed={'127.0.0.1:8768','localhost:8768','localhost'}|{h.strip() for h in os.getenv('HAVEN_ALLOWED_HOSTS','').split(',') if h.strip()}
  if host in allowed:
   return True
  self.reply({'error':'This service accepts local workspace requests only'},403);return False
 def do_GET(self):
  if not self.valid_host():return
  path=self.path.split('?')[0]
  if path=='/api/auth/status':return self.reply({'enrolled':AUTH.enrolled,'authenticated':AUTH.authenticated(self.headers.get('Cookie')),'remote':BIND not in ('127.0.0.1','localhost')})
  if path.startswith('/api/') and AUTH.enrolled and not AUTH.authenticated(self.headers.get('Cookie')):return self.reply({'error':'Sign in to this workspace'},401)
  if path=='/api/esp/setup':
   if self.client_address[0] not in ('127.0.0.1','::1'):return self.reply({'error':'ESP setup is local-only'},403)
   if not AUTH.enrolled:return self.reply({'error':'Create a workspace sign-in first'},403)
   return self.reply(ESP_SETUP.status())
  if path=='/api/email/settings':return self.reply(EMAIL.status())
  if path=='/api/push/status':return self.reply({'configured':WebPush().configured,'enrolled':AUTH.enrolled,'publicKey':os.getenv('HAVEN_VAPID_PUBLIC_KEY') if WebPush().configured else None,**PUSH.summary()})
  if path=='/api/models/deleted':return self.reply(MODELS.deleted_ids())
  if path=='/api/models':return self.reply(MODELS.list())
  if path.startswith('/api/models/'):
   try:
    import mimetypes
    parts=path.split('/')
    if len(parts)!=6 or parts[4]!='file':raise ValueError('Invalid model path')
    file,name=MODELS.file(parts[3],int(parts[5]));return self.reply(file.read_bytes(),content_type=mimetypes.guess_type(name)[0] or 'application/octet-stream')
   except (ValueError,TypeError) as exc:return self.reply({'error':str(exc)},400)
  if path=='/api/state':
   home=get_config() or {};nodes=NODES.snapshot();active=home.get('activeModuleId') or next((m['id'] for m in home.get('modules',[])),None)
   value=json.loads(json.dumps(nodes.get(active,radar.STATE)))
   with WIFI.lock:
    from wifi_transport import LINK_TIMEOUT_SECONDS
    wifi_online={module_id:bool(channel and not channel.closed and 0<=channel.now()-channel.last_seen<=LINK_TIMEOUT_SECONDS) for module_id,channel in WIFI.channels.items()}
   for module_id,node in nodes.items():node['transport_online']=wifi_online.get(module_id,False) or bool(node.get('connected'))
   value.update(transport_online=wifi_online.get(active,False) or bool(value.get('connected')),radar_uart=RADAR_BYTES.summary(active),csi=CSI.summary(active),availableDevices=DISCOVERY.list(),nodes=nodes,ports=radar.ports(),now=time.time(),events=home.get('events',[]),syncRecords=SYNC.list(),pushStatus={'configured':WebPush().configured,'enrolled':AUTH.enrolled,**PUSH.summary()})
   value['motionEvidence']=motion_evidence(value['csi'],value,value['now'])
   value['activityEstimate']=ACTIVITY_RUNTIME.estimate(active,value,CSI.export(active),value['now'])
   return self.reply(value)
  path=self.path.split('?')[0]
  if path=='/api/home':return self.reply(get_config())
  if path in ('/api/dataset/sessions','/api/dataset/training-export') or path.startswith('/api/dataset/sessions/'):
   try:
    if path=='/api/dataset/sessions':return self.reply(ACTIVITY_SESSIONS.list())
    if path=='/api/dataset/training-export':return self.reply(ACTIVITY_SESSIONS.bundle())
    return self.reply(ACTIVITY_SESSIONS.get(path.split('/')[-1]))
   except ValueError as exc:return self.reply({'error':str(exc)},400)
  if path=='/api/capabilities':return self.reply({'polycam_api_configured':Polycam().configured,'google_calendar_configured':GoogleCalendar().configured,'google_tasks_configured':GoogleTasks().configured,'point_cloud':'partial console previews','human_count':False,'activity_classifier':False,'vitals':False,'fall_detection':False,'csi':any(CSI.summary(m['id'])['connected'] for m in (get_config() or {}).get('modules',[])),'csi_activity_classifier':False,'trained_fusion':False,'listen':BIND,'wifi_transport':True,'wifi_hardware_verified':any(n.get('transport')=='wifi' and n.get('radar_verified') for n in NODES.snapshot().values())})
  if path in ('/api/polycam/captures','/api/polycam/artifacts'):
   try:
    from urllib.parse import parse_qs,urlparse
    value=Polycam().captures() if path.endswith('/captures') else Polycam().artifacts(parse_qs(urlparse(self.path).query).get('id',[''])[0])
    return self.reply(value)
   except (ValueError,RuntimeError) as exc:return self.reply({'error':str(exc)},400)
  if path=='/api/radar/raw':return self.reply(RADAR_BYTES.export((get_config() or {}).get('activeModuleId') or next((m['id'] for m in (get_config() or {}).get('modules',[])),None)))
  if path=='/api/csi/export':
   home=get_config() or {};active=home.get('activeModuleId') or next((m['id'] for m in home.get('modules',[])),None)
   node=NODES.snapshot().get(active,{})
   return self.reply({'source':'ESP32-S3 router LLTF CSI','moduleId':active,'label':'unlabelled','samples':CSI.export(active),
    'radar_frames':node.get('frames',[]),'radar_verified':node.get('radar_verified',False),
    'timing':'CSI device milliseconds; radar host receipt time. Not acquisition-synchronized.',
    'placement':next((m for m in home.get('modules',[]) if m['id']==active),None)})
  if path=='/api/wifi/inventory':return self.reply(inventory(DISCOVERY,DEVICE_KEYS,WIFI,get_config() or {}))
  if path=='/api/wifi/devices':return self.reply(DISCOVERY.list())
  if path=='/api/export':
   from urllib.parse import urlparse,parse_qs
   home=get_config() or {};module_id=parse_qs(urlparse(self.path).query).get('moduleId',[home.get('activeModuleId') or next((m['id'] for m in home.get('modules',[])),None)])[0]
   node=NODES.snapshot().get(module_id)
   return self.reply({'source':'live ESP console preview','moduleId':module_id,'complete_binary_cloud':False,'version':node.get('version') if node else None,'frames':node.get('frames',[]) if node else []})
  if path.startswith('/api/'):return super().do_GET()
  relative='index.html' if path=='/' else path.lstrip('/')
  file=(ROOT/'dist'/relative).resolve()
  if not file.is_relative_to((ROOT/'dist').resolve()):return self.reply({'error':'Invalid path'},400)
  if not file.exists():file=ROOT/'dist'/'index.html'
  if not file.exists():return self.reply({'error':'Run npm run build or use the Vite development server'},404)
  import mimetypes
  return self.reply(file.read_bytes(),content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
 def do_POST(self):
  if not self.valid_host():return
  origin=self.headers.get('Origin')
  if origin and not self.origin_allowed():return self.reply({'error':'Cross-origin request rejected'},403)
  if self.path=='/api/wifi/discover':
   import ssl
   if origin or (self.client_address[0] not in ('127.0.0.1','::1') and not isinstance(self.connection,ssl.SSLSocket)):return self.reply({'error':'Device discovery requires HTTPS'},403)
   try:
    size=int(self.headers.get('Content-Length',0))
    if not 0<size<=1024:raise ValueError('Invalid discovery packet')
    return self.reply(DISCOVERY.announce(json.loads(self.rfile.read(size))))
   except (ValueError,TypeError) as exc:return self.reply({'error':str(exc)},400)
  if self.path=='/api/wifi/exchange':
   # ESP credentials are separate from browser accounts and authorize this route only.
   import ssl
   if self.client_address[0] not in ('127.0.0.1','::1') and not isinstance(self.connection,ssl.SSLSocket):return self.reply({'error':'ESP delivery requires HTTPS'},403)
   if origin:return self.reply({'error':'Use the dedicated ESP transport'},403)
   try:
    size=int(self.headers.get('Content-Length',0))
    if not 0<size<=32000:raise ValueError('Device packet too large')
    body=json.loads(self.rfile.read(size));module_id=body.get('moduleId') if isinstance(body,dict) else None
    authorization=self.headers.get('Authorization','')
    token=authorization[7:] if authorization.startswith('Bearer ') else ''
    with WIFI.lock:
     if not isinstance(module_id,str) or not DEVICE_KEYS.verify(module_id,token):return self.reply({'error':'Invalid device credential'},401)
     if not any(m['id']==module_id for m in (get_config() or {}).get('modules',[])):raise ValueError('Choose a registered module')
     response=WIFI.exchange(module_id,body,NODES)
     if 'radar_uart' in body:RADAR_BYTES.ingest(module_id,body.get('boot'),body['radar_uart'],body.get('radar_dropped_bytes',0))
     if 'csi' in body:CSI.ingest(module_id,body.get('boot'),body['csi'],body.get('csi_dropped',0))
     PAIRED_CAPTURES.observe(module_id,NODES.snapshot().get(module_id,{}),CSI.export(module_id))
     return self.reply(response)
   except (ValueError,TypeError) as exc:return self.reply({'error':str(exc)},400)
  if self.path in ('/api/auth/setup','/api/auth/login','/api/auth/logout'):
   try:
    size=int(self.headers.get('Content-Length',0))
    if size<0 or size>4096:raise ValueError('Request too large')
    body=json.loads(self.rfile.read(size) or b'{}')
    if not isinstance(body,dict):raise ValueError('Expected a JSON object')
    if self.path=='/api/auth/setup':
     if self.client_address[0] not in ('127.0.0.1','::1'):raise ValueError('Create the workspace password locally before enabling remote access')
     token=AUTH.setup(body.get('password'))
    elif self.path=='/api/auth/login':token=AUTH.login(body.get('password'))
    else:AUTH.logout(self.headers.get('Cookie'));token=''
    value=json.dumps({'authenticated':bool(token)}).encode();self.send_response(200)
    cookie='haven_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age='+('43200' if token else '0')+('; Secure' if TLS else '')
    self.send_header('Set-Cookie',cookie);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(value)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(value);return
   except (ValueError,TypeError) as exc:return self.reply({'error':str(exc)},400)
  if AUTH.enrolled and not AUTH.authenticated(self.headers.get('Cookie')):return self.reply({'error':'Sign in to this workspace'},401)
  if self.path in ('/api/esp/setup','/api/esp/flash'):
   if self.client_address[0] not in ('127.0.0.1','::1') or not AUTH.enrolled:return self.reply({'error':'Use signed-in local workspace ESP setup'},403)
   try:
    size=int(self.headers.get('Content-Length',0))
    if not 0<size<=4096:raise ValueError('Invalid setup request')
    body=json.loads(self.rfile.read(size))
    if self.path=='/api/esp/flash':
     with NODES.lock:
      occupied=[node.STATE.get('port') for node in NODES.nodes.values() if node.WORKER and node.WORKER.is_alive()]
     return self.reply(ESP_SETUP.start(body,occupied),202)
    result=ESP_SETUP.save(body)
    if result['endpointChanged']:
     context=globals().get('device_tls')
     if context is not None:
      context.load_cert_chain(os.environ['HAVEN_DEVICE_TLS_CERT'],os.environ['HAVEN_DEVICE_TLS_KEY'])
      os.environ['HAVEN_ALLOWED_HOSTS']=body['host']+':8769'
     else:result['restartRequired']=True
    return self.reply(result)
   except ValueError as exc:return self.reply({'error':str(exc)},400)
   except (TypeError,OSError):return self.reply({'error':'Check the Wi-Fi settings and local toolchain. No private credentials are shown.'},400)
  if self.path in ('/api/email/settings','/api/email/test'):
   try:
    if self.client_address[0] not in ('127.0.0.1','::1'):raise ValueError('Configure email locally')
    size=int(self.headers.get('Content-Length',0))
    if not 0<size<=8192:raise ValueError('Invalid settings size')
    body=json.loads(self.rfile.read(size))
    if self.path=='/api/email/settings':return self.reply(EMAIL.save(body))
    if not EMAIL.enqueue(test=True):raise ValueError('Save email settings first, or wait for queued emails')
    return self.reply({'accepted':True})
   except (ValueError,TypeError):return self.reply({'error':'Check email settings and save them before testing'},400)

  if self.path=='/api/csi/calibrate':
   try:
    home=get_config() or {};active=home.get('activeModuleId') or next((m['id'] for m in home.get('modules',[])),None)
    if not CSI.summary(active)['connected']:raise ValueError('Connect the CSI stream first')
    CSI.calibrate(active);return self.reply({'status':'calibrating','seconds':30})
   except ValueError as exc:return self.reply({'error':str(exc)},400)
  if self.path in ('/api/wifi/pair','/api/wifi/reset','/api/wifi/revoke','/api/wifi/approve','/api/wifi/forget'):
   try:
    if not AUTH.enrolled and not (self.path=='/api/wifi/reset' and self.client_address[0] in ('127.0.0.1','::1')):raise ValueError('Create a workspace password before pairing an ESP')
    size=int(self.headers.get('Content-Length',0))
    if not 0<size<=4096:raise ValueError('Invalid pairing request')
    body=json.loads(self.rfile.read(size));module_id=body.get('moduleId') if isinstance(body,dict) else None
    if not any(m['id']==module_id for m in (get_config() or {}).get('modules',[])):raise ValueError('Choose a registered module')
    with WIFI.lock,NODES.lock:
     node=NODES.get(module_id)
     if node.WORKER and node.WORKER.is_alive():raise ValueError('Disconnect this module before changing Wi-Fi pairing')
     if self.path=='/api/wifi/approve' and DEVICE_KEYS.has_key(module_id) and DEVICE_KEYS.bindings().get(module_id)!=body.get('deviceId'):
      raise ValueError('This sensor already has a pairing. Choose an unused sensor, or explicitly revoke its existing Wi-Fi key first.')
     if self.path=='/api/wifi/forget':
      device_id=body.get('deviceId')
      if not isinstance(device_id,str):raise ValueError('Choose an ESP to forget')
      DEVICE_KEYS.forget(module_id,device_id)
      WIFI.disconnect(module_id)
      DISCOVERY.forget(device_id)
      return self.reply({'forgotten':True,'moduleId':module_id,'deviceId':device_id})
     WIFI.disconnect(module_id)
     if self.path=='/api/wifi/approve':
      DISCOVERY.approve(body.get('deviceId'),module_id,DEVICE_KEYS)
      return self.reply({'added':True,'moduleId':module_id})
     if self.path=='/api/wifi/pair':return self.reply({'moduleId':module_id,'deviceToken':DEVICE_KEYS.issue(module_id)})
     if self.path=='/api/wifi/revoke':DEVICE_KEYS.revoke(module_id)
    return self.reply({'reset':True,'moduleId':module_id})
   except (ValueError,TypeError) as exc:return self.reply({'error':str(exc)},400)
  if self.path in ('/api/push/subscribe','/api/push/unsubscribe'):
   try:
    if not AUTH.enrolled:raise ValueError('Create a workspace password before subscribing a device')
    size=int(self.headers.get('Content-Length',0))
    if not 0<size<=4096:raise ValueError('Invalid subscription size')
    body=json.loads(self.rfile.read(size))
    if self.path.endswith('/subscribe'):
     if not WebPush().configured:raise ValueError('Web Push is not configured')
     key=PUSH.subscribe(body);return self.reply({'saved':True,'deviceId':key})
    if not isinstance(body,dict) or not isinstance(body.get('endpoint'),str):raise ValueError('Invalid subscription endpoint')
    PUSH.unsubscribe(body['endpoint']);return self.reply({'removed':True})
   except (ValueError,TypeError) as exc:return self.reply({'error':str(exc)},400)
  if self.path.startswith('/api/models/') and self.path.endswith('/delete'):
   try:
    parts=self.path.split('/')
    if len(parts)!=5:raise ValueError('Invalid model path')
    with connection(DB) as db:
     db.execute('BEGIN IMMEDIATE')
     row=db.execute('SELECT value FROM config WHERE id=1').fetchone()
     home=json.loads(row[0]) if row else {}
     # Archive the original map references alongside the removed assets.
     MODELS.delete(parts[3],home)
     archive=MODELS.root/'.deleted'/parts[3]/'layout-before-delete.json'
     archive.write_text(json.dumps(home));archive.chmod(0o600)
     updated=without_deleted_scans(home)
     if row:db.execute('UPDATE config SET value=? WHERE id=1',(json.dumps(updated),))
    return self.reply({'deleted':True,'config':updated})
   except (ValueError,TypeError,OSError) as exc:return self.reply({'error':str(exc)},400)
  if self.path=='/api/models' or self.path.startswith('/api/models/'):
   try:
    length=int(self.headers.get('Content-Length',0))
    if self.path=='/api/models':
     if length<0 or length>100000:raise ValueError('Model metadata too large')
     return self.reply({'missing':MODELS.prepare(json.loads(self.rfile.read(length)))})
    parts=self.path.split('/')
    if len(parts)!=6 or parts[4]!='file':raise ValueError('Invalid model path')
    MODELS.upload(parts[3],int(parts[5]),self.rfile,length);return self.reply({'saved':True})
   except (ValueError,TypeError,KeyError) as exc:return self.reply({'error':str(exc)},400)
  if self.path in ('/api/connect','/api/disconnect','/api/scan','/api/stop','/api/monitoring'):
   origin=self.headers.get('Origin')
   if origin and not self.origin_allowed():return self.reply({'error':'Cross-origin request rejected'},403)
   try:
    size=int(self.headers.get('Content-Length',0))
    if size<0 or size>4096:raise ValueError('Request too large')
    body=json.loads(self.rfile.read(size) or b'{}')
    if not isinstance(body,dict):raise ValueError('Expected a JSON object')
    home=get_config() or {};module_id=body.get('moduleId') or home.get('activeModuleId') or next((m['id'] for m in home.get('modules',[])),None)
    if not any(m['id']==module_id for m in home.get('modules',[])):raise ValueError('Choose a registered module')
    if self.path=='/api/monitoring':NODES.set_monitoring(module_id,body.get('enabled'))
    elif self.path=='/api/connect':NODES.connect(module_id,body.get('port'))
    else:
     NODES.control(module_id,self.path.split('/')[-1])
     if self.path=='/api/disconnect':WIFI.disconnect(module_id,pause=True)
    return self.reply({'accepted':True,'moduleId':module_id})
   except (ValueError,TypeError) as exc:return self.reply({'error':str(exc)},400)
  if self.path=='/api/events/clear':
   with NODES.lock:
    with connection(DB) as db:
     db.execute('BEGIN IMMEDIATE')
     row=db.execute('SELECT value FROM config WHERE id=1').fetchone()
     if row:
      home=json.loads(row[0]);home['events']=[];home['eventsClearedAt']=time.time()
      db.execute('UPDATE config SET value=? WHERE id=1',(json.dumps(home),))
    NODES.rules={key:AwayRule() for key in NODES.rules}
   return self.reply({'cleared':True})
  if self.path in ('/api/dataset/export','/api/dataset/save','/api/dataset/review','/api/dataset/delete'):
   try:
    size=int(self.headers.get('Content-Length',0))
    if not 0<size<=4096:raise ValueError('Invalid session metadata size')
    from dataset import annotated_snapshot
    body=json.loads(self.rfile.read(size))
    if not isinstance(body,dict):raise ValueError('Expected session metadata')
    if self.path=='/api/dataset/delete':return self.reply(ACTIVITY_SESSIONS.delete(body.get('id'),body.get('confirm')))
    if self.path=='/api/dataset/review':return self.reply(ACTIVITY_SESSIONS.review(body.get('id'),body.get('state'),body.get('label'),body.get('notes'),body.get('confirmObserved')))
    value=annotated_snapshot(get_config() or {},NODES.snapshot(),body)
    from csi_recordings import attach
    attach(value,PAIRED_CAPTURES.samples(value['module_id'],value['frames'],CSI.export(value['module_id'])))
    return self.reply(ACTIVITY_SESSIONS.save(value) if self.path.endswith('/save') else value)
   except (ValueError,TypeError) as exc:return self.reply({'error':str(exc)},400)
  if self.path in ('/api/calendar/sync','/api/tasks/sync'):
   origin=self.headers.get('Origin')
   if origin and not self.origin_allowed():return self.reply({'error':'Cross-origin request rejected'},403)
   try:
    size=int(self.headers.get('Content-Length',0))
    if size<0 or size>4096:raise ValueError('Request too large')
    body=json.loads(self.rfile.read(size) or b'{}')
    trial=next((t for t in (get_config() or {}).get('trials',[]) if t['id']==body.get('trialId')),None)
    if not trial:raise ValueError('Trial not found')
    attempt=SYNC.begin(trial,'tasks' if self.path=='/api/tasks/sync' else 'calendar')
    try:
     results=(GoogleTasks() if self.path=='/api/tasks/sync' else GoogleCalendar()).sync(trial)
     outcome=SYNC.finish(attempt,results=results)
     return self.reply({'results':results,'sync':outcome})
    except (ValueError,RuntimeError,TypeError) as exc:
     SYNC.finish(attempt,error=str(exc));raise
   except (ValueError,RuntimeError,TypeError) as exc:return self.reply({'error':str(exc)},400)
  if self.path=='/api/home':
   origin=self.headers.get('Origin')
   if origin and not self.origin_allowed():return self.reply({'error':'Cross-origin request rejected'},403)
   try:
    n=int(self.headers.get('Content-Length',0))
    if n<0 or n>1000000:raise ValueError('Configuration too large')
    save_config(json.loads(self.rfile.read(n)));return self.reply({'saved':True})
   except (ValueError,TypeError,KeyError) as exc:return self.reply({'error':str(exc)},400)
  return super().do_POST()

if __name__=='__main__':
 if os.getenv('HAVEN_LOCAL_TIME_KEY'):
  from lan_time import serve as serve_lan_time
  threading.Thread(target=serve_lan_time,args=(os.environ['HAVEN_LOCAL_TIME_BIND'],os.environ['HAVEN_LOCAL_TIME_KEY']),daemon=True).start()
 threading.Thread(target=monitor,daemon=True).start()
 threading.Thread(target=push_monitor,daemon=True).start()
 print('Haven local service: http://127.0.0.1:8768',flush=True)
 if BIND not in ('127.0.0.1','localhost') and (not AUTH.enrolled or not TLS or not os.getenv('HAVEN_ALLOWED_HOSTS')):raise SystemExit('Remote binding requires a locally enrolled password, TLS certificate/key and explicit allowed hosts')
 service=ThreadingHTTPServer((BIND,8768),Handler)
 if TLS:
  import ssl
  context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(os.environ['HAVEN_TLS_CERT'],os.environ['HAVEN_TLS_KEY']);service.socket=context.wrap_socket(service.socket,server_side=True)
 device_service=None
 if os.getenv('HAVEN_DEVICE_TLS_CERT') and os.getenv('HAVEN_DEVICE_TLS_KEY'):
  import ssl
  class DeviceHandler(Handler):
   def do_GET(self):return self.reply({'error':'Device endpoint only'},404)
   def do_POST(self):
    if self.path not in ('/api/wifi/exchange','/api/wifi/discover'):return self.reply({'error':'Device endpoint only'},404)
    return super().do_POST()
  from tls_server import DeviceTLSServer
  device_tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);device_tls.minimum_version=ssl.TLSVersion.TLSv1_2
  device_tls.load_cert_chain(os.environ['HAVEN_DEVICE_TLS_CERT'],os.environ['HAVEN_DEVICE_TLS_KEY'])
  device_service=DeviceTLSServer((os.getenv('HAVEN_DEVICE_BIND','127.0.0.1'),int(os.getenv('HAVEN_DEVICE_PORT','8769'))),DeviceHandler,device_tls)
  threading.Thread(target=device_service.serve_forever,daemon=True).start()
  print('Haven HTTPS device listener ready',flush=True)
 try:service.serve_forever()
 finally:
  if device_service:device_service.shutdown();device_service.server_close()
  NODES.shutdown()
