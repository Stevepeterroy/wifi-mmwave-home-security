"""Numeric JSON forest inference, without loading executable pickle files."""
import json,math,struct
from pathlib import Path
from dataset import LABELS

FEATURE_COUNTS={'radar':50,'csi':250,'fusion':300}

def export_forest(model,branch,evaluation):
 return {'schema':'haven-target-rf-v1','domain':'reviewed Haven radar/CSI recordings',
  'branch':branch,'feature_count':int(model.n_features_in_),'classes':model.classes_.tolist(),
  'evaluation':evaluation,'trees':[{'left':e.tree_.children_left.tolist(),'right':e.tree_.children_right.tolist(),
   'feature':e.tree_.feature.tolist(),'threshold':e.tree_.threshold.tolist(),
   'values':e.tree_.value[:,0,:].tolist()} for e in model.estimators_]}

class Forest:
 def __init__(self,value):
  if not isinstance(value,dict):raise ValueError('Expected a numeric model package')
  if value.get('schema')!='haven-target-rf-v1' or value.get('domain')!='reviewed Haven radar/CSI recordings':raise ValueError('Use a Haven target-domain model')
  self.branch=value.get('branch');self.features=value.get('feature_count');self.classes=value.get('classes');self.trees=value.get('trees')
  if self.branch not in FEATURE_COUNTS or self.features!=FEATURE_COUNTS[self.branch]:raise ValueError('Model feature format mismatch')
  if not isinstance(self.classes,list) or not 2<=len(self.classes)<=len(LABELS)-1 or any(not isinstance(c,str) or c not in LABELS-{'unlabelled'} for c in self.classes) or len(set(self.classes))!=len(self.classes):raise ValueError('Invalid model classes')
  if not isinstance(self.trees,list) or not 1<=len(self.trees)<=250:raise ValueError('Invalid forest size')
  for tree in self.trees:
   if not isinstance(tree,dict):raise ValueError('Expected numeric tree arrays')
   n=len(tree.get('left',[]))
   if not 1<=n<=10000 or any(not isinstance(tree.get(k),list) or len(tree[k])!=n for k in ('right','feature','threshold','values')):raise ValueError('Invalid tree arrays')
   reached=set();stack=[0]
   while stack:
    i=stack.pop()
    if i in reached:raise ValueError('Repeated tree node')
    reached.add(i);left=tree['left'][i];right=tree['right'][i]
    if type(left) is not int or type(right) is not int:raise ValueError('Invalid child index')
    if left==-1 and right==-1:
     votes=tree['values'][i]
     if not isinstance(votes,list) or len(votes)!=len(self.classes) or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in votes) or sum(votes)<=0:raise ValueError('Invalid leaf votes')
    elif not (i<left<n and i<right<n and type(tree['feature'][i]) is int and 0<=tree['feature'][i]<self.features and type(tree['threshold'][i]) in (int,float) and math.isfinite(tree['threshold'][i])):raise ValueError('Invalid tree split')
    else:stack.extend((left,right))
   if len(reached)!=n:raise ValueError('Unreachable tree nodes')
  self.evaluation=value.get('evaluation',{})
 def probabilities(self,features):
  if len(features)!=self.features or any(type(x) not in (int,float) or not math.isfinite(x) for x in features):raise ValueError('Invalid model input features')
  # scikit-learn evaluates tree input as float32, including near split boundaries.
  try:values=[struct.unpack('f',struct.pack('f',x))[0] for x in features]
  except (OverflowError,struct.error) as exc:raise ValueError('Model input exceeds float32 range') from exc
  if not all(math.isfinite(x) for x in values):raise ValueError('Nonfinite float32 model input')
  votes=[0.0]*len(self.classes)
  for tree in self.trees:
   node=0
   while tree['left'][node]!=-1:
    node=tree['left'][node] if values[tree['feature'][node]]<=tree['threshold'][node] else tree['right'][node]
   total=sum(tree['values'][node])
   for k,v in enumerate(tree['values'][node]):votes[k]+=v/total/len(self.trees)
  return dict(zip(self.classes,votes))
 def predict(self,features):
  votes=self.probabilities(features);label=max(self.classes,key=lambda c:votes[c])
  return {'label':label,'model_vote':votes[label],'votes':votes,'branch':self.branch,
   'basis':'Experimental estimate from operator-reviewed target recordings; not independent ground truth'}

def load(path):
 p=Path(path)
 if p.stat().st_size>32*1024*1024:raise ValueError('Model package exceeds 32 MB')
 return Forest(json.loads(p.read_bytes()))
