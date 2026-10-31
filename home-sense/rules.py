"""Grouped motion episodes, not occupancy or medical inference."""
import time,uuid,copy
from room_geometry import reflection_in_room
from datetime import datetime,timezone

def stamp(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
class AwayRule:
 def __init__(self):self.last=None;self.motion_times=[];self.unmapped_times=[];self.trigger_samples=[]
 def evaluate(self,home,state,now=None):
  now=time.time() if now is None else now
  module=next((m for m in home.get('modules',[]) if m['id']==home.get('activeModuleId')),next(iter(home.get('modules',[])),None))
  if not module:return None
  previous=next((e for e in home.get('events',[]) if e.get('moduleId')==module['id'] and e.get('status')=='open'),None)
  enabled=home.get('away') and home.get('dataSource')=='live'
  if previous and (not enabled or now-previous['lastMotionEpoch']>=240):
   self.motion_times=[];self.unmapped_times=[];self.trigger_samples=[]
   return {**previous,'status':'closed','endedAt':stamp(now),'stopReason':'Away mode disabled' if not enabled else 'Four-minute quiet timeout; presence unknown','newEpisode':False}
  frame=state.get('last_frame')
  if not enabled or not state.get('connected') or not state.get('radar_verified') or not frame or not 0<=now-frame.get('received_at',0)<=1.5:
   self.motion_times=[];self.unmapped_times=[];self.trigger_samples=[];return None
  key=(frame['sequence'],frame['received_at'])
  if key==self.last:return None
  self.last=key
  # Console previews are sparse: empty reports often interleave genuine moving
  # reflections. Require three distinct motion-bearing reports in a short window
  # rather than three consecutive reports, without treating CSI alone as proof.
  self.motion_times=[t for t in self.motion_times if 0<=frame['received_at']-t<=8]
  self.unmapped_times=[t for t in self.unmapped_times if 0<=frame['received_at']-t<=8]
  self.trigger_samples=[s for s in self.trigger_samples if 0<=frame['received_at']-s['epoch']<=8]
  region=next((r for r in home.get('rooms',[]) if r['id']==module.get('roomId')),None)
  moving=[p for p in frame['points'] if abs(p['velocity_cm_s'])>=50] if frame['reported_points']>0 else []
  localized=any(not region or not region.get('boundary') or reflection_in_room(p,module,region) for p in moving)
  unmapped=bool(moving) and not localized
  if moving and not previous:
   self.trigger_samples.append({'epoch':frame['received_at'],'at':stamp(frame['received_at']),'sequence':frame['sequence'],'points':copy.deepcopy(frame['points'][:10])})
  if localized:self.motion_times.append(frame['received_at'])
  elif unmapped:self.unmapped_times.append(frame['received_at'])
  # A misaligned room polygon must not silently discard repeated radar motion.
  # Require stronger evidence and explicitly mark its location as unverified.
  if not moving or (not previous and len(self.motion_times)<3 and len(self.unmapped_times)<5):return None
  if previous and now-previous['lastMotionEpoch']<1:return None
  location_unverified=not previous and len(self.motion_times)<3
  event=copy.deepcopy(previous) if previous else {'id':str(uuid.uuid4()),'at':stamp(now),'room':('Near '+(region['name'] or module.get('name','sensor'))+' — location unverified') if location_unverified and region else region['name'] if region else 'Unassigned room','kind':'Moving radar reflections while away — review needed','source':'live','acknowledged':False,'moduleId':module['id'],'status':'open','locationUnverified':location_unverified,'placement':copy.deepcopy(module),'modelId':home.get('homeModelId'),'samples':[],'sampleCount':0,'recordingLimit':120,'cooldownSeconds':240}
  event.update(lastMotionEpoch=now,lastMotionAt=stamp(now),newEpisode=previous is None)
  if previous is None:
   event['samples']=[{k:v for k,v in sample.items() if k!='epoch'} for sample in self.trigger_samples]
   event['sampleCount']=len(event['samples'])
   if event['samples']:event['at']=event['samples'][0]['at']
   self.trigger_samples=[]
  else:
   event['sampleCount']+=1
  # Bounded console previews: preserve initial trigger and latest history, never claim full acquisition.
  if len(event['samples'])>=120:event['samples'].pop(1);event['recordingTruncated']=True
  if previous is not None:event['samples'].append({'at':stamp(now),'sequence':frame['sequence'],'points':copy.deepcopy(frame['points'][:10])})
  event['partialConsolePreview']=True
  event['pointLimitPerPreview']=10
  event['sampleIntervalSeconds']=1
  return event
