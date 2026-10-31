"""Participant-held-out source study, including rate/sparsity ablations.

This evaluates MVRHAR only. Artificial thinning is not an RD-60 recording.
No classifier from this script is enabled in Haven's live sensor path.
"""
import argparse,hashlib,io,json,time,zipfile
from pathlib import Path
import numpy as np
import sklearn,joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score,classification_report,confusion_matrix,recall_score
from train_baseline import window_features

ROOT=Path(__file__).resolve().parent/'data/training/mvrhar'
SCHEMA='haven-mvrhar-source-study-v1'
VARIANTS=('native_24hz','thinned_5hz','thinned_5hz_random4')

def sample_indices(source_rate=24,target_rate=5,seconds=2):
    """Previous source frame for each target time; no interpolation or pooling."""
    if source_rate<=0 or target_rate<=0 or target_rate>source_rate or seconds<=0:
        raise ValueError('Invalid temporal rates')
    count=int(seconds*target_rate)
    if count<1:raise ValueError('Window has no samples')
    return np.floor(np.arange(count)*source_rate/target_rate).astype(int)

def record_frames(data):
    if data.ndim!=2 or data.shape[1]!=7 or not len(data) or not np.isfinite(data).all():
        raise ValueError('Expected finite MVRHAR CSV rows')
    ids=data[:,0].astype(np.int64)
    if not np.array_equal(ids,data[:,0]) or np.any(ids<0):raise ValueError('Invalid frame index')
    grouped={int(i):data[ids==i,1:5] for i in np.unique(ids)}
    return grouped,int(ids.min()),int(ids.max())

def thin_points(frames,seed,cap=4):
    if cap<1:raise ValueError('Point limit must be positive')
    rng=np.random.default_rng(seed)
    # Preserve empty frames and point identity: never pad/interpolate observations.
    return [p[np.sort(rng.choice(len(p),cap,replace=False))] if len(p)>cap else p.copy() for p in frames]

def stable_seed(file,start):
    return int.from_bytes(hashlib.sha256(f'{file}:{start}:42'.encode()).digest()[:8],'little')

def extract(archive_path,records):
    names=[r['file'] for r in records]
    if len(names)!=len(set(names)):raise ValueError('Duplicate recording manifest')
    values={v:[] for v in VARIANTS};metadata=[];sampled=sample_indices()
    with zipfile.ZipFile(archive_path) as archive:
        for index,record in enumerate(records):
            # Validate filename identity rather than trusting arbitrary manifest labels.
            label,view,person,sequence=Path(record['file']).stem.rsplit('-',3)
            if (label,view,person,sequence)!=(record['label'],record['view'],record['participant'],record['sequence']):
                raise ValueError('Recording identity does not match filename')
            with archive.open(record['file']) as stream:
                data=np.loadtxt(io.TextIOWrapper(stream),delimiter=',',skiprows=1,ndmin=2)
            grouped,first,last=record_frames(data)
            for start in range(first,last-47,48):
                frames=[grouped.get(i,np.empty((0,4))) for i in range(start,start+48)]
                low=[frames[i] for i in sampled]
                variants=(frames,low,thin_points(low,stable_seed(record['file'],start)))
                for name,cloud in zip(VARIANTS,variants):values[name].append(window_features(cloud))
                metadata.append({'file':record['file'],'label':record['label'],'participant':person,
                    'view':view,'start_frame':start,'end_frame_exclusive':start+48})
            if index%20==0:print(f'extracted {index+1}/{len(records)} recordings',flush=True)
    return {k:np.asarray(v,dtype=np.float32) for k,v in values.items()},metadata

def holdout(metadata,person):
    train=np.array([r['participant']!=person for r in metadata]);test=~train
    if not train.any() or not test.any():raise ValueError('Empty participant fold')
    training_files={r['file'] for r,selected in zip(metadata,train) if selected}
    testing_files={r['file'] for r,selected in zip(metadata,test) if selected}
    if training_files & testing_files:raise ValueError('Recording leakage')
    return train,test

def evaluate(y,pred,labels,metadata):
    result={'windows':len(y),'balanced_accuracy':float(balanced_accuracy_score(y,pred)),
        'labels':labels,'classification_report':classification_report(y,pred,labels=labels,output_dict=True,zero_division=0),
        'confusion_matrix':confusion_matrix(y,pred,labels=labels).tolist(),'by_view':{}}
    for view in sorted({r['view'] for r in metadata}):
        mask=np.array([r['view']==view for r in metadata])
        present=np.unique(y[mask]).tolist()
        result['by_view'][view]={'windows':int(mask.sum()),
            'balanced_accuracy':float(recall_score(y[mask],pred[mask],labels=present,average='macro',zero_division=0)),
            'labels_present':present,'score_basis':'Mean recall over classes actually present in this view'}
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args();root=args.root
    archive_path=root/'csvs-basic.zip';manifest=json.loads((root/'splits.json').read_text())
    source_hash=hashlib.sha256(archive_path.read_bytes()).hexdigest()
    expected=json.loads((Path(__file__).resolve().parent/'docs/mvrhar-ingestion.json').read_text())['archive_sha256']
    if source_hash!=expected:raise ValueError('Source archive integrity check failed')
    output=root/'participant-sparsity-study';output.mkdir(exist_ok=True)
    started=time.time();X,metadata=extract(archive_path,manifest['records'])
    y=np.array([r['label'] for r in metadata]);participants=sorted({r['participant'] for r in metadata});labels=sorted(set(y.tolist()))
    np.savez_compressed(output/'features.npz',**X)
    (output/'window-manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    report={'schema':SCHEMA,'source':'MVRHAR Basic','source_url':'https://github.com/Tianshi-Dai/MVRHAR',
        'source_archive_sha256':source_hash,'license':'CC BY-NC-SA 4.0','source_rate_hz':24,
        'window_seconds':2,'native_frames_per_window':48,'sampled_frame_offsets':sample_indices().tolist(),
        'thinning':'Previous-frame sampling at 5 Hz; seeded random cap of four points, without replacement',
        'source_units':'Original CSV XYZ/Doppler units unchanged; no assumed RD-60 axis/unit mapping',
        'split_policy':'Three leave-one-participant-out folds; both other people train. Whole recordings never cross a fold.',
        'selection_policy':'Fixed predeclared RF settings; no hyperparameter search or model selection on fold test results',
        'algorithm':{'n_estimators':200,'max_depth':16,'class_weight':'balanced','random_state':42,'n_jobs':2},
        'features':'42 temporal XYZ/Doppler moment, extent and visible-count features; no SNR/group column',
        'software':{'numpy':np.__version__,'scikit_learn':sklearn.__version__},
        'target_domain_validated':False,'live_inference_enabled':False,'variants':{}}
    for variant in VARIANTS:
        folds=[]
        for person in participants:
            train,test=holdout(metadata,person)
            model=RandomForestClassifier(**report['algorithm']);model.fit(X[variant][train],y[train])
            pred=model.predict(X[variant][test]);test_meta=[r for r,use in zip(metadata,test) if use]
            result=evaluate(y[test],pred,labels,test_meta)
            result.update(held_out_participant=person,train_windows=int(train.sum()),
                train_participants=[p for p in participants if p!=person],
                train_recordings=len({r['file'] for r,use in zip(metadata,train) if use}),
                test_recordings=len({r['file'] for r in test_meta}))
            joblib.dump(model,output/f'{variant}-holdout-{person}.joblib')
            # Every saved prediction is traceable to its original recording/window.
            (output/f'{variant}-holdout-{person}-predictions.json').write_text(json.dumps([
                {**r,'prediction':str(p)} for r,p in zip(test_meta,pred)],indent=2)+'\n')
            folds.append(result)
            print(variant,'held out',person,'balanced accuracy',round(result['balanced_accuracy'],4),flush=True)
        accuracies=[f['balanced_accuracy'] for f in folds]
        report['variants'][variant]={'folds':folds,'mean_fold_balanced_accuracy':float(np.mean(accuracies)),
            'min_fold_balanced_accuracy':min(accuracies),'max_fold_balanced_accuracy':max(accuracies)}
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    report['elapsed_seconds']=time.time()-started
    report['limitations']=['Only three source participants; folds are correlated, not independent trials',
        'Thinned source clouds do not reproduce RD-60 missing-data mechanisms or point ordering',
        'No empty-room, multi-person, falls or vital-sign validation',
        'Missing beginning/end frames outside observed CSV range are unknown; incomplete final windows are dropped',
        'Use actual labelled RD-60 sessions for final training/evaluation before enabling app predictions']
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Completed source study in',round(report['elapsed_seconds'],1),'seconds',flush=True)

if __name__=='__main__':main()
