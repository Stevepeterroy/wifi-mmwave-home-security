"""Prepare or train an offline RD-60 preview baseline from Haven reviews.

A training run is an experiment against operator labels, not a deployment gate.
Existing output folders are never overwritten. No trained file is loaded by Haven.
"""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import sklearn,joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report,confusion_matrix,recall_score
from target_dataset import extract,partition,FEATURE_NAMES

PARAMETERS={'n_estimators':200,'max_depth':16,'class_weight':'balanced','random_state':42,'n_jobs':2}


def score(truth,prediction,classes):
 present=np.unique(truth).tolist()
 return {'windows':len(truth),'mean_recall_over_present_classes':float(recall_score(truth,prediction,labels=present,average='macro',zero_division=0)),
  'classes_present':present,'classes_not_evaluated':sorted(set(classes)-set(present)),
  'labels':classes,'classification_report':classification_report(truth,prediction,labels=classes,output_dict=True,zero_division=0),
  'confusion_matrix':confusion_matrix(truth,prediction,labels=classes).tolist(),
  'interpretation':'Agreement with whole-session operator annotations; not independent ground-truth verification'}


def run(bundle_path,output,train=None,validation=None,test=None):
 bundle_path=Path(bundle_path);output=Path(output)
 if output.exists():raise ValueError('Output folder already exists; choose a new experiment folder')
 if bundle_path.stat().st_size>64*1024*1024:raise ValueError('Bundle exceeds 64 MB')
 raw=bundle_path.read_bytes();bundle=json.loads(raw)
 X,metadata,prepared=extract(bundle)
 if not len(X):raise ValueError('No windows pass timing/report quality checks; inspect and collect better recordings')
 fitting=any(v is not None for v in (train,validation,test))
 if fitting and not all(v is not None for v in (train,validation,test)):raise ValueError('Supply train, validation and test participant groups together')
 masks=partition(metadata,train,validation,test) if fitting else None
 y=np.asarray([m['label'] for m in metadata]);report={**prepared,'created_at':datetime.now(timezone.utc).isoformat(),
  'input_bundle_sha256':hashlib.sha256(raw).hexdigest(),'accepted_windows':len(X),'participants':sorted({m['participant_id'] for m in metadata}),
  'classes':sorted(set(y.tolist())),'mode':'offline_training' if fitting else 'prepare_only',
  'validation_basis':'Operator labels with participant-held-out splits; independent verification still required',
  'software':{'numpy':np.__version__,'scikit_learn':sklearn.__version__},'live_classifier_enabled':False,'trained_model':None}
 # Validate and fit before creating the output folder so invalid data leaves no partial experiment.
 model=None;predictions={}
 if masks is not None:
  model=RandomForestClassifier(**PARAMETERS);model.fit(X[masks['train']],y[masks['train']])
  report['algorithm']=PARAMETERS;report['split_participants']={'train':sorted(train),'validation':sorted(validation),'test':sorted(test)}
  report['selection_policy']='Fixed algorithm/features/quality thresholds. No test-based tuning or automatic deployment.'
  report['evaluation']={}
  classes=model.classes_.tolist()
  for split in ('validation','test'):
   mask=masks[split];pred=model.predict(X[mask]);selected=[m for m,use in zip(metadata,mask) if use]
   report['evaluation'][split]=score(y[mask],pred,classes)
   predictions[split]=[{**m,'prediction':str(p)} for m,p in zip(selected,pred)]
  report['trained_model']='target-preview-rf.joblib'
 output.mkdir(mode=0o700,parents=True,exist_ok=False)
 (output/'input-reviewed-bundle.json').write_bytes(raw)
 np.savez_compressed(output/'features.npz',X=X,y=y)
 (output/'window-manifest.json').write_text(json.dumps(metadata,indent=2,allow_nan=False)+'\n')
 if model is not None:
  joblib.dump(model,output/'target-preview-rf.joblib')
  for split,values in predictions.items():(output/f'{split}-predictions.json').write_text(json.dumps(values,indent=2,allow_nan=False)+'\n')
 (output/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
 hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()}
 (output/'artifact-manifest.json').write_text(json.dumps({'input_bundle_sha256':report['input_bundle_sha256'],'files':hashes,
  'feature_names':FEATURE_NAMES,'live_classifier_enabled':False},indent=2)+'\n')
 output.chmod(0o700)
 for p in output.iterdir():p.chmod(0o600)
 return report


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--train',nargs='+',help='Participant IDs for training; all groups must be disjoint')
 parser.add_argument('--validation',nargs='+');parser.add_argument('--test',nargs='+')
 args=parser.parse_args()
 try:report=run(args.bundle,args.output,args.train,args.validation,args.test)
 except (ValueError,OSError) as exc:parser.exit(2,str(exc)+'\n')
 print(json.dumps({'mode':report['mode'],'accepted_windows':report['accepted_windows'],'participants':report['participants'],
  'evaluation':report.get('evaluation'),'live_classifier_enabled':False},indent=2),flush=True)

if __name__=='__main__':main()
