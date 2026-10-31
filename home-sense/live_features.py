"""Dependency-free counterpart of target radar/CSI training features.

This produces features only. No classifier or activity prediction is implied.
"""
import math,statistics

def mean(v):return sum(v)/len(v)
def std(v):return math.sqrt(mean([(x-mean(v))**2 for x in v]))
def extent(v):return max(v)-min(v)

def radar_features(frames):
 if not frames:raise ValueError('No radar frames')
 summaries=[];reported=[];omitted=[];missing=[];zero=[]
 for f in frames:
  points=f['points'];count=f['reported_points']
  if points:
   axes=[[p[k]/100 for p in points] for k in ('x_cm','y_cm','z_cm','velocity_cm_s')]
   summaries.append([mean(v) for v in axes]+[std(v) for v in axes]+[extent(v) for v in axes]+[len(points),mean([abs(v) for v in axes[3]])])
  else:summaries.append([0]*14)
  reported.append(count);omitted.append((count-len(points))/count if count else 0)
  missing.append(int(count>0 and not points));zero.append(int(count==0))
 columns=list(zip(*summaries))
 return [fn(v) for fn in (mean,std,extent) for v in columns]+[mean(reported),std(reported),extent(reported),mean(omitted),std(omitted),extent(omitted),mean(missing),mean(zero)]

def csi_features(samples):
 if len(samples)<24:raise ValueError('too_few_csi_samples')
 if len({s['boot'] for s in samples})!=1 or len({s['channel'] for s in samples})!=1:raise ValueError('csi_boot_or_channel_change')
 gaps=[(b['device_ms']-a['device_ms'])/1000 for a,b in zip(samples,samples[1:])]
 if any(g<=0 or g>.2+1e-8 for g in gaps):raise ValueError('csi_device_time_gap')
 if samples[-1]['device_ms']-samples[0]['device_ms']<1400:raise ValueError('csi_short_time_coverage')
 if any(b['sequence']!=a['sequence']+1 for a,b in zip(samples,samples[1:])):raise ValueError('csi_sequence_gap')
 amplitudes=[]
 for sample in samples:
  iq=sample['iq'][4:];amp=[math.hypot(a,b) for a,b in zip(iq[::2],iq[1::2])]
  norm=math.sqrt(sum(a*a for a in amp))
  if norm==0:raise ValueError('csi_zero_amplitude')
  amplitudes.append([a/norm for a in amp])
 columns=list(zip(*amplitudes));deltas=[[abs(b-a) for a,b in zip(v,v[1:])] for v in columns]
 rssi=[s['rssi'] for s in samples]
 result=[fn(v) for fn in (mean,std,extent) for v in columns]+[mean(v) for v in deltas]+[mean(rssi),std(rssi)]
 if len(result)!=250 or not all(math.isfinite(v) for v in result):raise ValueError('csi_nonfinite_features')
 return result

def paired_window(frames,samples,start,end):
 """Use the same accepted host-time interval and quality limits as training."""
 if not all(type(v) in (int,float) and math.isfinite(v) for v in (start,end)) or abs(end-start-2) > 1e-6:raise ValueError('Use a finite two-second window')
 observed=[f for f in frames if start<=f['received_at']<end]
 if len(observed)<8:raise ValueError('too_few_reports')
 if observed[0]['received_at']-start>.4+1e-6 or end-observed[-1]['received_at']>.4+1e-6:raise ValueError('incomplete_time_coverage')
 if any(b['received_at']-a['received_at']>.6+1e-6 for a,b in zip(observed,observed[1:])):raise ValueError('receipt_gap')
 if any(b['sequence']!=a['sequence']+1 for a,b in zip(observed,observed[1:])):raise ValueError('missing_report_sequence')
 selected=[s for s in samples if start<=s['received_at']-s['age_ms']/1000<end]
 csi=csi_features(selected)
 times=[s['received_at']-s['age_ms']/1000 for s in selected]
 if min(times)-start>.4 or end-max(times)>.4:raise ValueError('csi_incomplete_host_time_coverage')
 radar=radar_features(observed)
 return {'radar':radar,'csi':csi,'fusion':radar+csi}
