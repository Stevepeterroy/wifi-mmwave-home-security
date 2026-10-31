"""Compare fixed CSI motion rules on explicitly timed operator-reported phases.

This is a within-session probe, not a generalization accuracy evaluation.
Thresholds use only the calibration phase. Transitions must be excluded by
the caller; host timestamps describe batch receipt rather than acquisition.
"""
import argparse
import datetime
import hashlib
import json
import statistics as stats
from pathlib import Path
from csi_motion import window_score


def analyze(capture, calibration, quiet, walking):
    if capture['summary'].get('capture_complete') is False:
        raise ValueError('Incomplete capture cannot establish a completed controlled trial')
    start = datetime.datetime.fromisoformat(capture['summary']['started_at']).timestamp()
    samples = capture['samples']
    if not samples or any(not isinstance(s.get('received_at'),(int,float)) for s in samples):
        raise ValueError('Timestamped samples are required for phase comparison')
    intervals = [calibration, quiet, walking]
    for a,b in intervals:
        if not 0 <= a < b or (b-a) % 2:
            raise ValueError('Phases must contain whole nonoverlapping two-second windows')
    for i,(a,b) in enumerate(intervals):
        for c,d in intervals[i+1:]:
            if max(a,c) < min(b,d): raise ValueError('Overlapping phases')
    if len({s['boot'] for s in samples}) != 1 or len({s['channel'] for s in samples}) != 1:
        raise ValueError('Probe requires one boot and one channel')
    results = {}
    for method in ('adjacent', 'temporal_variation'):
        phases = {}
        for name,(a,b) in zip(('calibration','quiet_probe','walking_probe'),intervals):
            windows = []
            for t in range(a,b,2):
                selected = [s for s in samples if start+t <= s['received_at'] < start+t+2]
                windows.append({'host_interval_seconds':[t,t+2], 'packets':len(selected),
                                'score':window_score(selected,method)})
            phases[name] = windows
        scores = [w['score'] for w in phases['calibration'] if w['score'] is not None]
        threshold = None
        if len(scores) >= 12:
            median = stats.median(scores)
            mad = stats.median(abs(s-median) for s in scores)
            threshold = max(median+6*1.4826*mad,median*1.5,.005)
        summary = {}
        for name in ('quiet_probe','walking_probe'):
            for window in phases[name]:
                window['above_threshold'] = (window['score'] > threshold
                    if threshold is not None and window['score'] is not None else None)
            valid = [w for w in phases[name] if w['above_threshold'] is not None]
            summary[name] = {'valid':len(valid), 'total':len(phases[name]),
                             'above_threshold':sum(w['above_threshold'] for w in valid)}
        results[method] = {'threshold':threshold,'valid_calibration_windows':len(scores),
                           'phases':phases,'summary':summary}
    return {'methods':results,'label_basis':'Operator-reported phases; confirm protocol adherence separately',
            'threshold_formula':'max(median+6*1.4826*MAD, median*1.5, 0.005)',
            'limitations':['Single session, participant and placement; not generalization accuracy',
                           'Host batch receipt times approximate phase boundaries',
                           'Quiet data can contain a stationary occupant; no occupancy inference',
                           'Rejected windows remain unknown and are included in coverage counts']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture',type=Path)
    p.add_argument('--calibration',nargs=2,type=int,required=True)
    p.add_argument('--quiet',nargs=2,type=int,required=True)
    p.add_argument('--walking',nargs=2,type=int,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=analyze(json.loads(args.capture.read_text()),args.calibration,args.quiet,args.walking)
    result['source']=str(args.capture)
    result['source_sha256']=hashlib.sha256(args.capture.read_bytes()).hexdigest()
    with args.output.open('x') as output:output.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v['summary'] | {'threshold':v['threshold']} for k,v in result['methods'].items()},indent=2))


if __name__=='__main__':main()
