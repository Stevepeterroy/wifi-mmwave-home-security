"""Independent diagnostic transports with exclusive physical-port ownership."""
import importlib.util,json,threading,time,sys
from datetime import datetime
from pathlib import Path
from rules import AwayRule
SOURCE=Path(__file__).resolve().parent.parent/'radar-demo'/'server.py'
if str(SOURCE.parent) not in sys.path:sys.path.append(str(SOURCE.parent))
class NodeRegistry:
 def __init__(self):self.lock=threading.RLock();self.nodes={};self.rules={};self.monitoring={};self.rule_cursors={}
 def get(self,node_id):
  if not isinstance(node_id,str) or not node_id or len(node_id)>100:raise ValueError('Choose a registered module')
  with self.lock:
   if node_id not in self.nodes:
    spec=importlib.util.spec_from_file_location('haven_node_'+str(len(self.nodes)),SOURCE)
    node=importlib.util.module_from_spec(spec);spec.loader.exec_module(node)
    self.nodes[node_id]=node;self.rules[node_id]=AwayRule();self.monitoring[node_id]=False;self.rule_cursors[node_id]=None
    base=node.EspReader
    class ManagedReader(base):
     def scan(reader):
      node.set_state(scan_error=None)
      try:
       super(ManagedReader,reader).scan()
       node.set_state(scan_cycles=node.STATE.get('scan_cycles',0)+1)
      except Exception as exc:
       node.set_state(scan_error=str(exc));raise
    node.EspReader=ManagedReader
   return self.nodes[node_id]
 def snapshot(self):
  result={}
  with self.lock:
   for key,node in self.nodes.items():
    with node.LOCK:result[key]={**json.loads(json.dumps(node.STATE)),'monitoring':self.monitoring[key]}
  return result
 def connect(self,node_id,port):
  with self.lock:
   node=self.get(node_id)
   if node.WORKER and node.WORKER.is_alive():raise ValueError('This module already has an open reader')
   for other in self.nodes.values():
    if other.WORKER and other.WORKER.is_alive() and other.STATE['port']==port:raise ValueError('This serial port is already assigned to another module')
   if port not in [p['port'] for p in node.ports()]:raise ValueError('Select an available USB serial port')
   self.monitoring[node_id]=False
   node.set_state(scan_error=None,scan_cycles=0,port=port,transport='usb',message='Connecting…',frames=[],last_frame=None,status={},logs=[],version=None,connected=False,radar_verified=False,stop_acknowledged=None)
   node.WORKER=node.EspReader(port);node.WORKER.start()
 def control(self,node_id,job):
  with self.lock:
   node=self.get(node_id)
   if job in ('stop','disconnect'):self.monitoring[node_id]=False
   if job=='disconnect':
    if node.WORKER:node.WORKER.close_requested.set()
    return
   if not node.WORKER or not node.WORKER.is_alive() or not node.STATE['radar_verified']:raise ValueError('Connect and verify this module first')
   with node.LOCK:
    if job=='scan':
     if node.STATE['scan_running'] or node.STATE['scan_pending']:raise ValueError('This module is already scanning or preparing')
     node.set_state(scan_pending=True,message='Preparing the live scan…')
    node.WORKER.jobs.put(job)
 def retire_wifi(self,node_id):
  with self.lock:
   node=self.get(node_id);worker=node.WORKER
   if worker and worker.is_alive() and node.STATE.get('transport')!='wifi':raise ValueError('Disconnect the USB reader before Wi-Fi recovery')
   self.monitoring[node_id]=False
   if worker:worker.close_requested.set()
  if worker and worker.is_alive():worker.join(2)
 def connect_wifi(self,node_id,channel):
  with self.lock:
   node=self.get(node_id)
   if node.WORKER and node.WORKER.is_alive():raise ValueError('This module already has an open reader; disconnect it before Wi-Fi pairing')
   self.monitoring[node_id]=False
   node.set_state(scan_error=None,scan_cycles=0,port='wifi:'+node_id,transport='wifi',message='Wi-Fi ESP connected; verifying diagnostics…',frames=[],last_frame=None,status={},logs=[],version=None,connected=False,radar_verified=False,stop_acknowledged=None)
   node.WORKER=node.EspReader('wifi:'+node_id,transport=channel);node.WORKER.start()
 def set_monitoring(self,node_id,enabled):
  if not isinstance(enabled,bool):raise ValueError('Monitoring must be true or false')
  with self.lock:
   node=self.get(node_id)
   if enabled:
    if not node.WORKER or not node.WORKER.is_alive() or not node.STATE['radar_verified'] or node.STATE.get('version')!='V4.130.4.2':raise ValueError('Monitoring requires a connected radar with the verified firmware version')
    if node.STATE.get('stop_acknowledged') is False:raise ValueError('The radar did not acknowledge stop. Reconnect and verify before monitoring.')
    node.set_state(scan_error=None)
   self.monitoring[node_id]=enabled
   if not enabled and node.WORKER and node.WORKER.is_alive() and (node.STATE['scan_running'] or node.STATE['scan_pending']):node.WORKER.jobs.put('stop')
 def tick(self):
  with self.lock:
   for key,node in self.nodes.items():
    if not self.monitoring[key]:continue
    with node.LOCK:
     alive=node.WORKER and node.WORKER.is_alive()
     if not alive or not node.STATE['connected'] or not node.STATE['radar_verified'] or node.STATE.get('scan_error') or node.STATE.get('stop_acknowledged') is False:
      self.monitoring[key]=False
      node.set_state(message='Monitoring stopped: connection, scan, or stop acknowledgment needs review.')
      continue
     if not node.STATE['scan_running'] and not node.STATE['scan_pending']:
      node.set_state(scan_pending=True,message='Monitoring: preparing the next finite scan. Reports pause during setup.')
      node.WORKER.jobs.put('scan')
 def evaluate(self,home,now=None):
  if not home:return []
  now=time.time() if now is None else now
  snapshots=self.snapshot();events=[]
  for module in home['modules']:
   key=module['id']
   if key not in snapshots:continue
   state=snapshots[key];cursor=self.rule_cursors[key]
   frames=sorted(state.get('frames') or [],key=lambda f:(f['received_at'],f['sequence']))
   if not frames and state.get('last_frame'):frames=[state['last_frame']]
   # Wi-Fi delivers several radar reports together. Looking only at last_frame
   # misses motion reports when a later empty report arrives in the same batch.
   fresh=[f for f in frames if (f['received_at'],f['sequence'])>cursor and f['received_at']<=now] if cursor else [f for f in frames if 0<=now-f['received_at']<=8]
   local={**home,'activeModuleId':key,'events':list(home.get('events',[]))}
   for frame in fresh:
    self.rule_cursors[key]=(frame['received_at'],frame['sequence'])
    event=self.rules[key].evaluate(local,{**state,'last_frame':frame},frame['received_at'])
    if event:
     event['moduleId']=key;events.append(event)
     local['events']=[e for e in local['events'] if e['id']!=event['id']]+[event]
   if not fresh:
    event=self.rules[key].evaluate(local,state,now)
    if event:event['moduleId']=key;events.append(event)
  return events
 def shutdown(self):
  with self.lock:
   for key,node in self.nodes.items():
    self.monitoring[key]=False
    if node.WORKER:node.WORKER.close_requested.set()
