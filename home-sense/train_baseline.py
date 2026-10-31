"""Source-domain temporal point-cloud baseline; not a validated RD-60 model."""
import io,json,zipfile,hashlib
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report,confusion_matrix,balanced_accuracy_score
import joblib

ROOT=Path(__file__).resolve().parent/'data/training/mvrhar'

def window_features(frames):
    """Framewise XYZ/velocity moments, extents and point count; no SNR."""
    features=[]
    for points in frames:
        if len(points):
            features.append(np.r_[points.mean(0),points.std(0),np.ptp(points,axis=0),len(points),np.abs(points[:,3]).mean()])
        else:features.append(np.zeros(14))
    f=np.asarray(features)
    return np.r_[f.mean(0),f.std(0),np.ptp(f,axis=0)]

def main():
    manifest=json.loads((ROOT/'splits.json').read_text())
    sets={k:([],[],[]) for k in ['train','validation','test']}
    with zipfile.ZipFile(ROOT/'csvs-basic.zip') as archive:
        for index,record in enumerate(manifest['records']):
            with archive.open(record['file']) as stream:
                data=np.loadtxt(io.TextIOWrapper(stream),delimiter=',',skiprows=1,ndmin=2)
            if data.shape[1]!=7 or not np.isfinite(data).all():raise ValueError('Invalid data: '+record['file'])
            ids=data[:,0].astype(int)
            if not np.array_equal(ids,data[:,0]) or np.any(ids<0):raise ValueError('Invalid frame index')
            grouped={int(i):data[ids==i,1:5] for i in np.unique(ids)}
            # Keep absent frames empty; never concatenate across recordings.
            first,last=int(ids.min()),int(ids.max())
            X,y,origins=sets[record['split']]
            for start in range(first,last-47,48):
                X.append(window_features([grouped.get(i,np.empty((0,4))) for i in range(start,start+48)]))
                y.append(record['label']);origins.append(record['file'])
            if index%20==0:print('processed',index+1,flush=True)
    model=RandomForestClassifier(n_estimators=200,max_depth=16,class_weight='balanced',random_state=42,n_jobs=2)
    model.fit(sets['train'][0],sets['train'][1])
    result={'algorithm':'RandomForest temporal statistics baseline','window_frames':48,'window_seconds_at_source_rate':2,'features':'XYZ/Doppler frame moments, extents and count; no SNR','split':'participant 00 train, 01 validation, 02 test; nonoverlapping windows','target_domain_validated':False,'source_archive_sha256':hashlib.sha256((ROOT/'csvs-basic.zip').read_bytes()).hexdigest(),'evaluation':{}}
    for split in ['validation','test']:
        X,y,origins=sets[split];pred=model.predict(X)
        result['evaluation'][split]={'windows':len(y),'balanced_accuracy':balanced_accuracy_score(y,pred),'classification_report':classification_report(y,pred,output_dict=True,zero_division=0),'labels':model.classes_.tolist(),'confusion_matrix':confusion_matrix(y,pred,labels=model.classes_).tolist()}
    joblib.dump(model,ROOT/'source-baseline.joblib')
    (ROOT/'source-baseline-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print({s:r['balanced_accuracy'] for s,r in result['evaluation'].items()},flush=True)

if __name__=='__main__':main()
