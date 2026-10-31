"""Approximate host-time paired windows; rejects missing or discontinuous CSI."""
import numpy as np
from target_dataset import extract as radar_extract, FEATURE_NAMES as RADAR_FEATURE_NAMES
from csi_recordings import quality,estimated_received_time

CSI_FEATURE_NAMES=[f'csi.{stat}.{i}' for stat in ('mean','std','range','delta') for i in range(62)]+['csi.rssi_mean','csi.rssi_std']

def csi_features(samples):
 if len(samples)<24:raise ValueError('too_few_csi_samples')
 if len({s['boot'] for s in samples})!=1 or len({s['channel'] for s in samples})!=1:raise ValueError('csi_boot_or_channel_change')
 gaps=np.diff([s['device_ms'] for s in samples])/1000
 if np.any(gaps<=0) or np.any(gaps>.2+1e-8):raise ValueError('csi_device_time_gap')
 if samples[-1]['device_ms']-samples[0]['device_ms']<1400:raise ValueError('csi_short_time_coverage')
 if any(b['sequence']!=a['sequence']+1 for a,b in zip(samples,samples[1:])):raise ValueError('csi_sequence_gap')
 iq=np.asarray([s['iq'][4:] for s in samples],dtype=float).reshape(-1,62,2)
 amp=np.linalg.norm(iq,axis=2);norm=np.linalg.norm(amp,axis=1)
 if np.any(norm==0):raise ValueError('csi_zero_amplitude')
 amp=amp/norm[:,None];rssi=np.asarray([s['rssi'] for s in samples],dtype=float)
 values=np.r_[amp.mean(0),amp.std(0),np.ptp(amp,axis=0),np.mean(np.abs(np.diff(amp,axis=0)),axis=0),rssi.mean(),rssi.std()]
 if not np.isfinite(values).all():raise ValueError('csi_nonfinite_features')
 return values

def extract(bundle):
 radar,metadata,report=radar_extract(bundle)
 sources={record['capture']['source_sha256']:record['capture'] for record in bundle['sessions']}
 vectors=[];radar_vectors=[];accepted=[];rejected=[]
 for vector,m in zip(radar,metadata):
  capture=sources[m['source_sha256']];q=quality(capture)
  selected=[s for s in capture.get('csi_samples',[]) if m['start_received_at']<=estimated_received_time(s)<m['end_received_at_exclusive']]
  reason=None
  if not q['paired']:reason='no_continuous_overlapping_csi'
  else:
   try:
    v=csi_features(selected)
    estimated=[estimated_received_time(s) for s in selected]
    if min(estimated)-m['start_received_at']>.4 or m['end_received_at_exclusive']-max(estimated)>.4:reason='csi_incomplete_host_time_coverage'
   except ValueError as exc:reason=str(exc)
  if reason:rejected.append({**m,'reason':reason,'csi_samples':len(selected)});continue
  vectors.append(v);radar_vectors.append(vector)
  accepted.append({**m,'csi_samples':len(selected),'csi_boot':selected[0]['boot'],'csi_channel':selected[0]['channel'],
   'csi_device_times':[s['device_ms'] for s in selected],'csi_estimated_host_times':estimated,
   'csi_sha256':capture['csi_sha256']})
 r=np.asarray(radar_vectors).reshape(-1,len(RADAR_FEATURE_NAMES));c=np.asarray(vectors).reshape(-1,len(CSI_FEATURE_NAMES))
 return {'radar':r,'csi':c,'fusion':np.c_[r,c]},accepted,{**report,'schema':'haven-paired-preview-csi-features-v1',
  'paired_rejected_windows':rejected,'csi_feature_names':CSI_FEATURE_NAMES,
  'pairing':'Shared module, overlapping estimated host-time windows; device acquisition synchronization not verified',
  'live_classifier_enabled':False}
