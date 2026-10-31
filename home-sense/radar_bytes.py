"""Bounded, unparsed UART1 byte evidence. Never claims complete point clouds."""
import base64,threading,time
from collections import deque
class RadarBytes:
 def __init__(self):self.lock=threading.RLock();self.streams={}
 def ingest(self,module,boot,chunks,dropped=0):
  if not isinstance(chunks,list) or len(chunks)>4:raise ValueError('Invalid radar UART batch')
  if type(dropped) is not int or not 0<=dropped<2**32:raise ValueError('Invalid radar UART drop count')
  checked=[]
  for c in chunks:
   if not isinstance(c,dict):raise ValueError('Invalid radar UART chunk')
   for key,low,high in [('sequence',1,2**32-1),('device_ms',0,2**32-1),('age_ms',0,1000)]:
    if type(c.get(key)) is not int or not low<=c[key]<=high:raise ValueError('Invalid radar UART metadata')
   encoded=c.get('data')
   if not isinstance(encoded,str) or len(encoded)>684:raise ValueError('Invalid radar UART bytes')
   try:data=base64.b64decode(encoded,validate=True)
   except (ValueError,TypeError):raise ValueError('Invalid radar UART encoding') from None
   if not 0<len(data)<=512:raise ValueError('Invalid radar UART length')
   checked.append({**c,'bytes':len(data),'received_at':time.time()})
  with self.lock:
   s=self.streams.setdefault(module,{'boot':boot,'sequence':0,'bytes':0,'chunks':deque(maxlen=128),'sequence_gaps':0,'dropped_bytes':0})
   if s['boot']!=boot:s.update(boot=boot,sequence=0,bytes=0,chunks=deque(maxlen=128),sequence_gaps=0,dropped_bytes=0)
   for c in checked:
    if c['sequence']<=s['sequence']:continue
    s['sequence_gaps']+=max(0,c['sequence']-s['sequence']-1);s['sequence']=c['sequence'];s['bytes']+=c['bytes'];s['chunks'].append(c)
   s['dropped_bytes']=dropped
 def summary(self,module):
  with self.lock:
   s=self.streams.get(module)
   return {'bytes':s['bytes'] if s else 0,'retained_bytes':sum(c['bytes'] for c in s['chunks']) if s else 0,'dropped_bytes':s['dropped_bytes'] if s else 0,'sequence_gaps':s['sequence_gaps'] if s else 0,'decoded':False,'complete_point_cloud':False}
 def export(self,module):
  with self.lock:return {'source':'RD-60 UART1 raw bytes','moduleId':module,'boot':self.streams.get(module,{}).get('boot'),'summary':self.summary(module),'chunks':list(self.streams.get(module,{}).get('chunks',[])),'limitations':'Unparsed base64 chunks; last 128 retained, maximum 64 KiB. Not packet-validated or guaranteed lossless. Device ms and host receipt times are not acquisition-synchronized.'}
