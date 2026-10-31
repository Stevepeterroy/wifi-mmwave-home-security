"""Evaluate radar-only, CSI-only and feature fusion on identical target windows."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from paired_dataset import extract
from target_dataset import partition
from train_target import score
from rf_runtime import export_forest

def run(bundle_path,output,train,validation,test):
 output=Path(output)
 if output.exists():raise ValueError('Choose a new experiment output folder')
 raw=Path(bundle_path).read_bytes()
 if len(raw)>64*1024*1024:raise ValueError('Reviewed bundle exceeds 64 MB')
 matrices,metadata,quality=extract(json.loads(raw))
 if not metadata:raise ValueError('No paired windows pass quality checks; collect and review simultaneous CSI/radar sessions')
 masks=partition(metadata,train,validation,test);y=np.asarray([m['label'] for m in metadata])
 classes=sorted(set(y.tolist()))
 for name,mask in masks.items():
  if set(y[mask])!=set(classes):raise ValueError(name+' split must contain every activity for a comparable evaluation')
 report={**quality,'input_sha256':hashlib.sha256(raw).hexdigest(),'accepted_windows':len(metadata),
  'split_participants':{'train':train,'validation':validation,'test':test},'branches':{},
  'selection_policy':'Fixed RF configuration; identical paired windows and participant splits for every branch',
  'trained_fusion_enabled':False,'target_deployment_validated':False}
 models={};predictions={}
 for branch,x in matrices.items():
  model=RandomForestClassifier(n_estimators=200,max_depth=16,class_weight='balanced',random_state=42,n_jobs=2)
  model.fit(x[masks['train']],y[masks['train']]);models[branch]=model
  report['branches'][branch]={}
  for split in ('validation','test'):
   pred=model.predict(x[masks[split]])
   report['branches'][branch][split]=score(y[masks[split]],pred,classes)
   predictions[branch+'-'+split]=[{**m,'prediction':str(p)} for m,p in zip([v for v,use in zip(metadata,masks[split]) if use],pred)]
 test_scores={name:v['test']['mean_recall_over_present_classes'] for name,v in report['branches'].items()}
 report['fusion_test_recall_delta_vs_radar']=test_scores['fusion']-test_scores['radar']
 report['fusion_test_recall_delta_vs_csi']=test_scores['fusion']-test_scores['csi']
 report['interpretation']='Agreement with operator labels; an observed difference on these participants is not universal accuracy improvement'
 output.mkdir(mode=0o700,parents=True)
 (output/'input-reviewed-bundle.json').write_bytes(raw)
 (output/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False))
 (output/'window-manifest.json').write_text(json.dumps(metadata,indent=2,allow_nan=False))
 np.savez_compressed(output/'features.npz',**matrices,y=y)
 for name,model in models.items():
  joblib.dump(model,output/(name+'-rf.joblib'))
  (output/(name+'-rf.json')).write_text(json.dumps(export_forest(model,name,{'metrics':report['branches'][name],
   'input_sha256':report['input_sha256'],'split_participants':report['split_participants'],
   'recorded_module_ids':sorted({m['module_id'] for m in metadata}),
   'live_enabled':False,'independent_ground_truth':False}),allow_nan=False))
 for name,values in predictions.items():(output/(name+'-predictions.json')).write_text(json.dumps(values,indent=2,allow_nan=False))
 for file in output.iterdir():file.chmod(0o600)
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 for name in ('train','validation','test'):p.add_argument('--'+name,nargs='+',required=True)
 a=p.parse_args()
 try:result=run(a.bundle,a.output,a.train,a.validation,a.test)
 except (ValueError,OSError) as exc:p.exit(2,str(exc)+'\n')
 print(json.dumps({'accepted_windows':result['accepted_windows'],'branches':result['branches'],
  'fusion_test_recall_delta_vs_radar':result['fusion_test_recall_delta_vs_radar'],'trained_fusion_enabled':False},indent=2))
