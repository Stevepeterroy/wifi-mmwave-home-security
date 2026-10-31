"""Retain CSI for the latest completed finite scan until it is annotated."""
import copy,threading
from collections import OrderedDict
from csi_recordings import estimated_received_time

def key(frames):
 if not frames:return None
 return (frames[0].get('received_at'),frames[-1].get('received_at'),len(frames),frames[0].get('sequence'),frames[-1].get('sequence'))

class PairedCaptures:
 def __init__(self):self.lock=threading.RLock();self.captures=OrderedDict()
 def observe(self,module,node,samples):
  if node.get('scan_pending') or node.get('scan_running') or node.get('monitoring') or node.get('scan_error') or not node.get('radar_verified') or node.get('stop_acknowledged') is not True:return
  frames=node.get('frames',[]);identity=key(frames)
  if identity is None or not isinstance(identity[0],(int,float)) or not isinstance(identity[1],(int,float)):return
  selected=[s for s in samples if identity[0]-.4<=estimated_received_time(s)<=identity[1]+.4]
  with self.lock:
   previous=self.captures.get(module)
   if previous and previous['key']==identity and len(previous['samples'])>=len(selected):return
   self.captures[module]={'key':identity,'samples':copy.deepcopy(selected)}
   self.captures.move_to_end(module)
   while len(self.captures)>32:self.captures.popitem(last=False)
 def samples(self,module,frames,fallback):
  with self.lock:
   previous=self.captures.get(module)
   return copy.deepcopy(previous['samples']) if previous and previous['key']==key(frames) else fallback
