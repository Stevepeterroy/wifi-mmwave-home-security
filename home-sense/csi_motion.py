"""Quiet-baseline CSI change detector. Does not infer presence or activity."""
import math
import statistics as stats

def window_score(samples, method='adjacent'):
    if method not in ('adjacent', 'temporal_variation'):
        raise ValueError('Unknown CSI motion method')
    if len(samples) < 16: return None
    if len({s['boot'] for s in samples}) != 1 or len({s['channel'] for s in samples}) != 1: return None
    sequences = [s.get('sequence') for s in samples]
    if any(type(n) is not int for n in sequences): return None
    if any(b != a+1 for a,b in zip(sequences,sequences[1:])): return None
    times = [s['device_ms'] for s in samples]
    if times[-1] - times[0] < 1000 or any(not 0 < b-a <= 200 for a,b in zip(times,times[1:])): return None
    vectors = []
    for s in samples:
        iq = s['iq']
        # Discard the first four bytes on every packet so invalid words never enter.
        amplitudes = [math.hypot(iq[i],iq[i+1]) for i in range(4,128,2)]
        norm = math.sqrt(sum(a*a for a in amplitudes))
        if norm <= 0: return None
        vectors.append([a/norm for a in amplitudes])
    if method == 'temporal_variation':
        center = [stats.mean(row[i] for row in vectors) for i in range(len(vectors[0]))]
        return math.sqrt(stats.mean(sum((a-b)**2 for a,b in zip(row,center)) for row in vectors))
    return stats.median(math.sqrt(sum((a-b)**2 for a,b in zip(x,y))) for x,y in zip(vectors,vectors[1:]))

class MotionDetector:
    def __init__(self, method='adjacent'):
        if method not in ('adjacent', 'temporal_variation'): raise ValueError('Unknown CSI motion method')
        self.method = method
        self.calibrations = {}
    def start(self, module, samples):
        if not samples: raise ValueError('Connect the CSI stream first')
        last = samples[-1]
        self.calibrations[module] = {'boot':last['boot'], 'channel':last['channel'],
            'start':last['device_ms'], 'threshold':None}
    def state(self, module, samples, fresh):
        c = self.calibrations.get(module)
        if not c: return {'status':'needs_calibration', 'enabled':False}
        if not samples or samples[-1]['boot'] != c['boot'] or samples[-1]['channel'] != c['channel']:
            self.calibrations.pop(module,None)
            return {'status':'needs_calibration', 'enabled':False}
        if not fresh: return {'status':'unavailable', 'enabled':False}
        now = samples[-1]['device_ms']
        if c['threshold'] is None:
            elapsed = now-c['start']
            if elapsed < 30000: return {'status':'calibrating', 'enabled':False, 'remaining_seconds':max(0,math.ceil((30000-elapsed)/1000))}
            baseline = [s for s in samples if c['start'] < s['device_ms'] <= c['start']+30000]
            scores = [window_score([s for s in baseline if start <= s['device_ms'] < start+2000], self.method)
                for start in range(c['start'],c['start']+30000,2000)]
            valid = [s for s in scores if s is not None]
            if len(valid) < 12:
                self.calibrations.pop(module,None)
                return {'status':'calibration_failed', 'enabled':False}
            median = stats.median(valid); mad = stats.median(abs(s-median) for s in valid)
            c['threshold'] = max(median+6*1.4826*mad,median*1.5,0.005)
        score = window_score([s for s in samples if now-2000 <= s['device_ms'] <= now], self.method)
        if score is None: return {'status':'unavailable', 'enabled':False}
        return {'status':'motion' if score>c['threshold'] else 'quiet', 'enabled':True,
                'score':score, 'threshold':c['threshold'], 'method':('quiet-baseline temporal amplitude variation' if self.method == 'temporal_variation' else 'quiet-baseline channel change'),
                'validated_activity_model':False}
