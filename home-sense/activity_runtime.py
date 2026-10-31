"""Opt-in experimental target activity estimates; never care/vital inference."""
import math
from rf_runtime import load
from live_features import paired_window

class ActivityRuntime:
 def __init__(self,path=None):
  self.model=None;self.error=None;self.modules=set()
  if not path:return
  try:
   model=load(path);e=model.evaluation
   if not isinstance(e,dict):raise ValueError('Target evaluation metadata required')
   groups=e.get('split_participants',{})
   if not isinstance(groups,dict):raise ValueError('Participant split metadata required')
   values=[groups.get(k) for k in ('train','validation','test')]
   if any(not isinstance(v,list) or not v or any(not isinstance(p,str) or not p.strip() for p in v) for v in values):raise ValueError('Participant-separated target evaluation required')
   sets=[set(v) for v in values]
   if any(sets[a]&sets[b] for a,b in ((0,1),(0,2),(1,2))):raise ValueError('Evaluation participants overlap')
   metrics=e.get('metrics',{})
   if not isinstance(metrics,dict):raise ValueError('Held-out metrics required')
   for split in ('validation','test'):
    m=metrics.get(split,{})
    if not isinstance(m,dict):raise ValueError('Held-out metrics required')
    if m.get('labels')!=model.classes or m.get('classes_not_evaluated')!=[] or type(m.get('windows')) is not int or m['windows']<1:raise ValueError('Every model class needs held-out evaluation')
    score=m.get('mean_recall_over_present_classes')
    if type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1:raise ValueError('Invalid evaluation metrics')
   scope=e.get('recorded_module_ids')
   if not isinstance(scope,list) or not scope or any(not isinstance(m,str) or not m for m in scope):raise ValueError('Target module scope required')
   self.modules=set(scope);self.model=model
  except (OSError,ValueError,TypeError,KeyError) as exc:self.error=str(exc)
 def estimate(self,module,node,samples,now):
  if not self.model:return {'enabled':False,'status':'not_configured' if not self.error else 'model_rejected','reason':self.error}
  if module not in self.modules:return {'enabled':False,'status':'outside_training_scope'}
  frames=node.get('frames',[])
  if not node.get('connected') or not node.get('radar_verified') or not frames or not 0<=now-frames[-1].get('received_at',0)<2 or not samples or not 0<=now-samples[-1]['received_at']<3:return {'enabled':False,'status':'waiting_for_fresh_data'}
  end=frames[-1]['received_at']+.2
  try:
   features=paired_window(frames,samples,end-2,end)
   prediction=self.model.predict(features[self.model.branch])
  except (ValueError,KeyError,TypeError) as exc:return {'enabled':False,'status':'waiting_for_continuous_data','reason':str(exc)}
  return {'enabled':True,'status':'experimental_estimate',**prediction,'moduleId':module,
   'window_start':end-2,'window_end':end,'independently_validated':False,
   'people_identified':False,'medical_use':False}
