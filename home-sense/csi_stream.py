"""Validated raw LLTF CSI collection; no trained detection is implied."""
import threading,time,math
from collections import deque
from csi_motion import MotionDetector
class CsiStreams:
 def __init__(self):self.lock=threading.RLock();self.streams={};self.motion=MotionDetector()
 def calibrate(self,module):
  with self.lock:self.motion.start(module,list(self.streams.get(module,{}).get('samples',[])))
 def ingest(self,module,boot,samples,dropped=0):
  if not isinstance(samples,list) or len(samples)>16:raise ValueError('Invalid CSI batch')
  checked=[]
  for sample in samples:
   if not isinstance(sample,dict):raise ValueError('Invalid CSI sample')
   for field,lo,hi in [('sequence',1,2**32-1),('device_ms',0,2**32-1),('age_ms',0,1000),('rssi',-128,0),('channel',1,14)]:
    if type(sample.get(field)) is not int or not lo<=sample[field]<=hi:raise ValueError('Invalid CSI '+field)
   if type(sample.get('first_word_invalid')) is not bool:raise ValueError('Invalid CSI first word flag')
   iq=sample.get('iq')
   if not isinstance(iq,list) or len(iq)!=128 or any(type(v) is not int or not -128<=v<=127 for v in iq):raise ValueError('Invalid CSI IQ')
   checked.append({**sample,'received_at':time.time(),'boot':boot})
  if type(dropped) is not int or not 0<=dropped<2**32:raise ValueError('Invalid CSI drop count')
  with self.lock:
   stream=self.streams.setdefault(module,{'boot':boot,'samples':deque(maxlen=2000),'sequence':0,'received':0,'dropped':0})
   if stream['boot']!=boot:stream.update(boot=boot,samples=deque(maxlen=2000),sequence=0,received=0)
   for sample in checked:
    if sample['sequence']<=stream['sequence']:continue
    stream['samples'].append(sample);stream['sequence']=sample['sequence'];stream['received']+=1
   stream['dropped']=dropped
 def summary(self,module):
  with self.lock:
   s=self.streams.get(module)
   if not s or not s['samples']:return {'connected':False,'samples':0,'detection_enabled':False}
   samples=list(s['samples']);last=samples[-1];span=samples[-1]['received_at']-samples[0]['received_at']
   fresh=time.time()-last['received_at']<3;motion=self.motion.state(module,samples,fresh)
   return {'connected':fresh,'samples':s['received'],'retained':len(samples),'dropped':s['dropped'],'rssi':last['rssi'],'channel':last['channel'],'approx_rate':(len(samples)-1)/span if span>0 else 0,'detection_enabled':motion['enabled'],'motion':motion}
 def export(self,module):
  with self.lock:return list(self.streams.get(module,{}).get('samples',[]))
