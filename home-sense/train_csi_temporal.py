"""Exploratory ESP-Fi-HAR temporal benchmark; never installs a live model.

Select on participants 5/6; evaluate the selected candidate on 7/8.
The earlier baseline has already exposed this test set: this is a follow-up
benchmark, not an untouched confirmatory test or evidence of target accuracy.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import joblib
import numpy as np
from scipy.io import loadmat
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from train_csi_source import LABELS, features as baseline_features


def features(amplitude):
    a = np.asarray(amplitude, dtype=float)
    if a.shape == (52, 950):
        a = a.T
    if a.shape != (950, 52) or not np.isfinite(a).all():
        raise ValueError('Expected finite 950 x 52 amplitude')
    # Normalize each carrier to emphasize its temporal changes over static gain.
    centered = a - np.median(a, axis=0)
    scale = np.quantile(a, .75, axis=0) - np.quantile(a, .25, axis=0)
    z = np.clip(centered / np.maximum(scale, 1e-6), -10, 10)
    out = [baseline_features(a)]
    for chunks in (2, 4, 8):
        for part in np.array_split(z, chunks):
            out.extend((part.mean(0), part.std(0), np.mean(np.abs(np.diff(part, axis=0)), axis=0)))
    # Relative frequency only: archive acquisition rate is not assumed here.
    power = np.abs(np.fft.rfft(z * np.hanning(len(z))[:, None], axis=0)) ** 2
    power[0] = 0
    power /= np.maximum(power.sum(0), 1e-12)
    for band in np.array_split(power[1:], 8):
        out.append(band.sum(0))
    return np.concatenate(out).astype(np.float32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite an existing experiment')
    rows = []; seen = set()
    for path in sorted(args.root.rglob('*.mat')):
        match = re.fullmatch(r'(\d+)-(\d+)-(\d+)-(\d+)', path.stem)
        if not match:
            raise ValueError('Unrecognized trial identity: ' + str(path))
        scene, person, activity, trial = map(int, match.groups())
        identity = (scene, person, activity, trial)
        if identity in seen or not (1 <= scene <= 4 and 1 <= person <= 8 and 1 <= activity <= 7 and trial > 0):
            raise ValueError('Duplicate or invalid trial identity: ' + str(path))
        seen.add(identity)
        rows.append({'file': str(path.relative_to(args.root)), 'participant': person,
                     'scene': scene, 'activity': activity - 1,
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'x': features(loadmat(path)['CSIamp'])})
    if not rows:
        raise ValueError('No trials')
    x = np.stack([r['x'] for r in rows]); y = np.array([r['activity'] for r in rows])
    people = np.array([r['participant'] for r in rows])
    masks = {'train': people <= 4, 'validation': (people == 5) | (people == 6), 'test': people >= 7}
    for mask in masks.values():
        if set(y[mask]) != set(range(7)):
            raise ValueError('Split missing classes')
    train, validation, test = (masks[k] for k in ('train', 'validation', 'test'))
    candidates = [
        ('extra-trees', ExtraTreesClassifier(n_estimators=400, class_weight='balanced', random_state=42, n_jobs=4)),
        ('random-forest', RandomForestClassifier(n_estimators=300, class_weight='balanced', random_state=42, n_jobs=4)),
        *[(f'rbf-svm-C{c}', make_pipeline(StandardScaler(), SVC(C=c, class_weight='balanced')))
          for c in (1, 10, 100)],
    ]
    best = -1; selected = None; results = []
    for name, model in candidates:
        model.fit(x[train], y[train])
        prediction = model.predict(x[validation])
        score = balanced_accuracy_score(y[validation], prediction)
        result = {'name': name, 'validation_balanced_accuracy': score,
                  'validation_macro_f1': f1_score(y[validation], prediction, average='macro')}
        results.append(result); print(json.dumps(result), flush=True)
        if score > best:
            best = score; selected = (name, model)
    name, model = selected
    prediction = model.predict(x[test])
    report = {'source': 'https://github.com/AutoSmartGroup/ESP-Fi-HAR',
              'feature_version': 'espfi-temporal-relative-v1', 'labels': LABELS,
              'features': x.shape[1], 'trials': len(rows),
              'split_participants': {'train': [1,2,3,4], 'validation': [5,6], 'test': [7,8]},
              'split_counts': {k: int(v.sum()) for k,v in masks.items()},
              'candidates': results, 'selected': name,
              'test_balanced_accuracy': balanced_accuracy_score(y[test], prediction),
              'test_macro_f1': f1_score(y[test], prediction, average='macro'),
              'test_confusion_matrix': confusion_matrix(y[test], prediction, labels=range(7)).tolist(),
              'live_enabled': False, 'target_validated': False,
              'limitations': ['Follow-up on a previously observed test set; not confirmatory.',
                              'Source amplitude and sampling differ from target CSI.',
                              'No empty-room class; cannot validate occupancy.',
                              'No measured cross-link or radar-fusion improvement.']}
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = [{k: v for k,v in r.items() if k != 'x'} for r in rows]
    for r in manifest:
        r['split'] = 'train' if r['participant'] <= 4 else 'validation' if r['participant'] <= 6 else 'test'
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (args.output/'evaluation.json').write_text(json.dumps(report, indent=2)+'\n')
    (args.output/'test-predictions.json').write_text(json.dumps([
        {'file':r['file'], 'actual':int(r['activity']), 'predicted':int(p)}
        for r,p in zip([r for r in manifest if r['split']=='test'], prediction)], indent=2)+'\n')
    joblib.dump({'model': model, 'labels': LABELS, 'feature_version':report['feature_version'],
                 'live_enabled':False}, args.output/'model.joblib')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
