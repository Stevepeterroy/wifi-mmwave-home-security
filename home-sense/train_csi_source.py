"""ESP-Fi HAR baseline with participant-disjoint selection and evaluation.

This source model is an offline benchmark, never automatically enabled on S3.
The source archive supplies amplitude, not verified acquisition timestamps.
"""
import argparse, hashlib, json, re
from pathlib import Path
import joblib
import numpy as np
from scipy.io import loadmat
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score, confusion_matrix

LABELS = ['run', 'fall', 'walk', 'turn', 'jump', 'squat', 'arm_wave']

def features(amplitude):
    a = np.asarray(amplitude, dtype=float)
    if a.shape == (52, 950): a = a.T
    if a.shape != (950, 52) or not np.isfinite(a).all():
        raise ValueError('Expected finite 950 x 52 amplitude')
    a = (a - a.mean()) / max(a.std(), 1e-8)
    # Time-relative statistics; no invented sample rate or absolute frequencies.
    out = [a.mean(0), a.std(0), np.mean(np.abs(np.diff(a, axis=0)), axis=0),
           np.quantile(a, .9, axis=0) - np.quantile(a, .1, axis=0)]
    for part in np.array_split(a, 5): out.extend([part.mean(0), part.std(0)])
    return np.concatenate(out).astype(np.float32)

def main():
    p = argparse.ArgumentParser(); p.add_argument('root', type=Path)
    p.add_argument('--output', type=Path, default=Path('data/training/csi-source'))
    args = p.parse_args(); rows = []; seen = set()
    for path in sorted(args.root.rglob('*.mat')):
        match = re.fullmatch(r'(\d+)-(\d+)-(\d+)-(\d+)', path.stem)
        if not match: raise ValueError('Unrecognized trial identity: ' + str(path))
        scene, person, activity, trial = map(int, match.groups())
        identity = (scene, person, activity, trial)
        if identity in seen: raise ValueError('Duplicate trial: ' + str(identity))
        seen.add(identity)
        if not (1 <= scene <= 4 and 1 <= person <= 8 and 1 <= activity <= 7):
            raise ValueError('Invalid source label')
        mat = loadmat(path)
        if 'CSIamp' not in mat: raise ValueError('Missing CSIamp: ' + str(path))
        rows.append((features(mat['CSIamp']), activity - 1, person, str(path.relative_to(args.root))))
    if not rows: raise ValueError('No source trials')
    x = np.stack([r[0] for r in rows]); y = np.array([r[1] for r in rows])
    people = np.array([r[2] for r in rows])
    train = people <= 4; val = (people == 5) | (people == 6); test = people >= 7
    for mask in [train, val, test]:
        if set(y[mask]) != set(range(7)): raise ValueError('Split missing activity classes')
    candidates = []; selected = None; best = -1
    for depth in [8, 16, None]:
        model = RandomForestClassifier(n_estimators=250, max_depth=depth,
            class_weight='balanced', random_state=42, n_jobs=-1)
        model.fit(x[train], y[train]); score = balanced_accuracy_score(y[val], model.predict(x[val]))
        candidates.append({'max_depth': depth, 'validation_balanced_accuracy': score})
        if score > best: best = score; selected = model
    prediction = selected.predict(x[test])
    report = {'source': 'https://github.com/AutoSmartGroup/ESP-Fi-HAR', 'license': 'CC BY 4.0',
        'samples': len(rows), 'features': x.shape[1], 'labels': LABELS,
        'split_participants': {'train': [1,2,3,4], 'validation': [5,6], 'test': [7,8]},
        'split_counts': {'train': int(train.sum()), 'validation': int(val.sum()), 'test': int(test.sum())},
        'candidates': candidates, 'test_balanced_accuracy': balanced_accuracy_score(y[test], prediction),
        'test_macro_f1': f1_score(y[test], prediction, average='macro'),
        'test_confusion_matrix': confusion_matrix(y[test], prediction, labels=range(7)).tolist(),
        'live_enabled': False, 'target_validated': False,
        'limitations': ['ESP32 source; S3 transfer unvalidated', 'No quiet or empty-room class',
            'Source acquisition timing and subcarrier mapping not verified', 'No paired radar fusion evaluation']}
    args.output.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': selected, 'labels': LABELS, 'feature_version': 'espfi-relative-v1',
                 'live_enabled': False}, args.output / 'model.joblib')
    (args.output / 'evaluation.json').write_text(json.dumps(report, indent=2))
    (args.output / 'manifest.json').write_text(json.dumps([{'file':r[3], 'participant':r[2],
        'activity':LABELS[r[1]], 'split':'train' if r[2]<=4 else 'validation' if r[2]<=6 else 'test'} for r in rows], indent=2))
    print(json.dumps(report, indent=2))

if __name__ == '__main__': main()
