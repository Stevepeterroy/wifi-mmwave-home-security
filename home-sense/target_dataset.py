"""Prepare reviewed RD-60 previews for participant-held-out offline experiments.

Coordinates are converted from cm/cm/s to m/m/s in the radar's local axes.
No interpolation, padding, source-dataset unit assumptions or live inference.
"""
import hashlib,json,math
from pathlib import Path
import numpy as np
from activity_sessions import quality
from dataset import LABELS
from train_baseline import window_features

SCHEMA='haven-target-preview-features-v1'
FEATURE_NAMES=[f'{summary}.{feature}' for summary in ('mean','std','range') for feature in (
 'x_mean','y_mean','z_mean','velocity_mean','x_std','y_std','z_std','velocity_std',
 'x_extent','y_extent','z_extent','velocity_extent','visible_count','abs_velocity_mean')]+[
 'reported_count_mean','reported_count_std','reported_count_range',
 'omitted_fraction_mean','omitted_fraction_std','omitted_fraction_range',
 'coordinates_unavailable_fraction','zero_report_fraction']
WINDOW_SECONDS=2.0
MIN_REPORTS=8
MAX_GAP_SECONDS=.6
EDGE_TOLERANCE_SECONDS=.4


def identity(record):
 if not isinstance(record,dict):raise ValueError('Invalid saved session')
 cap=record.get('capture');q=quality(cap);review=record.get('review')
 if not isinstance(review,dict) or review.get('state')!='reviewed' or review.get('confirmed_observed') is not True:
  raise ValueError('Every input session needs an explicit operator review')
 label=review.get('label')
 if not isinstance(label,str) or label not in LABELS-{'unlabelled'} or not isinstance(review.get('notes'),str) or not review['notes'].strip():
  raise ValueError('Reviewed activity and observation notes are required')
 if not q['time_ordered'] or q['duration_seconds']<2:raise ValueError('Ordered host receipt timestamps spanning at least two seconds are required')
 if not math.isfinite(q['duration_seconds']) or q['duration_seconds']>3600:raise ValueError('Target preview sessions must span no more than one hour')
 if any(cap[k]!=cap[k].strip() for k in ('participant_id','session_id')):raise ValueError('Session identifiers must be trimmed')
 history=record.get('review_history')
 if not isinstance(history,list) or not history or not isinstance(history[-1],dict) or history[-1].get('review')!=review:raise ValueError('Latest review must match the retained review history')
 source={'source':cap['source'],'moduleId':cap['module_id'],'version':cap.get('firmware'),'frames':cap['frames']}
 expected=hashlib.sha256(json.dumps(source,sort_keys=True,allow_nan=False).encode()).hexdigest()
 if cap.get('source_sha256')!=expected:raise ValueError('Source snapshot hash mismatch')
 frames=cap['frames']
 if any(b['sequence']<=a['sequence'] for a,b in zip(frames,frames[1:])):raise ValueError('Report sequences must increase in acquisition order')
 return cap,review,q


def features(frames):
 clouds=[np.asarray([[p[k]/100 for k in ('x_cm','y_cm','z_cm','velocity_cm_s')] for p in f['points']],dtype=np.float64).reshape(-1,4) for f in frames]
 basic=window_features(clouds)
 reported=np.asarray([f['reported_points'] for f in frames],dtype=np.float64)
 visible=np.asarray([len(f['points']) for f in frames],dtype=np.float64)
 omitted=np.divide(reported-visible,reported,out=np.zeros_like(reported),where=reported>0)
 value=np.r_[basic,reported.mean(),reported.std(),np.ptp(reported),omitted.mean(),omitted.std(),np.ptp(omitted),
  np.mean((reported>0)&(visible==0)),np.mean(reported==0)]
 if value.shape!=(len(FEATURE_NAMES),) or not np.isfinite(value).all():raise ValueError('Invalid target window features')
 return value


def extract(bundle):
 if not isinstance(bundle,dict) or bundle.get('schema')!='haven-reviewed-preview-bundle-v1':raise ValueError('Use Haven’s reviewed dataset export')
 records=bundle.get('sessions')
 if not isinstance(records,list) or not records:raise ValueError('No reviewed target sessions available; collect and review real recordings first')
 if len(records)>500:raise ValueError('Session limit exceeded')
 X=[];metadata=[];rejected=[];sessions=[];hashes=set();names=set()
 for record in records:
  cap,review,q=identity(record);source=cap['source_sha256'];name=(cap['participant_id'].strip(),cap['session_id'].strip())
  if source in hashes or name in names:raise ValueError('Duplicate original capture or participant/session identity')
  hashes.add(source);names.add(name);frames=cap['frames'];first=frames[0]['received_at'];last=frames[-1]['received_at']
  emitted=0;skipped=0
  # Disjoint physical time intervals, not overlapping report-count windows.
  for index in range(math.floor((last-first+1e-8)/WINDOW_SECONDS)+1):
   start=first+index*WINDOW_SECONDS;end=start+WINDOW_SECONDS
   observed=[f for f in frames if start<=f['received_at']<end]
   reason=None
   if len(observed)<MIN_REPORTS:reason='too_few_reports'
   elif observed[0]['received_at']-start>EDGE_TOLERANCE_SECONDS+1e-6 or end-observed[-1]['received_at']>EDGE_TOLERANCE_SECONDS+1e-6:reason='incomplete_time_coverage'
   elif any(b['received_at']-a['received_at']>MAX_GAP_SECONDS+1e-6 for a,b in zip(observed,observed[1:])):reason='receipt_gap'
   elif any(b['sequence']!=a['sequence']+1 for a,b in zip(observed,observed[1:])):reason='missing_report_sequence'
   origin={'session_id':cap['session_id'],'participant_id':cap['participant_id'],'source_sha256':source,'module_id':cap['module_id'],
    'room_id':cap['room_id'],'label':review['label'],'window_index':index,'start_received_at':start,'end_received_at_exclusive':end}
   if reason:
    rejected.append({**origin,'reason':reason,'observed_reports':len(observed)});skipped+=1;continue
   vector=features(observed);X.append(vector);emitted+=1
   metadata.append({**origin,'report_sequences':[f['sequence'] for f in observed],'actual_receipt_times':[f['received_at'] for f in observed],
    'visible_points':sum(len(f['points']) for f in observed),'reported_points':sum(f['reported_points'] for f in observed),
    'incomplete_reports':sum(len(f['points'])<f['reported_points'] for f in observed),'placement':cap.get('placement'),
    'firmware':cap.get('firmware'),'room_geometry':cap.get('room_geometry'),'home_model_id':cap.get('home_model_id'),
    'physical_calibration_verified':cap.get('physical_calibration_verified',False),'label_basis':'Explicit whole-session operator review; not independently verified'})
  sessions.append({'participant_id':cap['participant_id'],'session_id':cap['session_id'],'source_sha256':source,'label':review['label'],
   'quality':q,'accepted_windows':emitted,'rejected_windows':skipped})
 values=np.asarray(X,dtype=np.float64).reshape(-1,len(FEATURE_NAMES))
 return values,metadata,{'schema':SCHEMA,'sessions':sessions,'rejected_windows':rejected,
  'window_seconds':WINDOW_SECONDS,'min_reports':MIN_REPORTS,'max_gap_seconds':MAX_GAP_SECONDS,'edge_tolerance_seconds':EDGE_TOLERANCE_SECONDS,
  'feature_names':FEATURE_NAMES,'coordinate_units':'m','velocity_units':'m/s','axes':'Local radar XYZ; physical mounting calibration unverified',
  'timing':'Host receipt timestamps, not radar acquisition timestamps','interpolation':False,'padding':False,
  'label_basis':'Explicit operator reviews; independent ground truth not established','live_classifier_enabled':False}


def partition(metadata,train,validation,test):
 groups=[set(v) for v in (train,validation,test)]
 if any(not g for g in groups) or any(groups[a]&groups[b] for a,b in ((0,1),(0,2),(1,2))):raise ValueError('Specify three nonempty, disjoint participant groups')
 available={m['participant_id'] for m in metadata}
 if set.union(*groups)!=available:raise ValueError('Every available participant must be assigned once, with no unknown IDs')
 masks={name:np.asarray([m['participant_id'] in group for m in metadata]) for name,group in zip(('train','validation','test'),groups)}
 if any(not mask.any() for mask in masks.values()):raise ValueError('Each split needs usable target windows')
 classes={m['label'] for m,use in zip(metadata,masks['train']) if use}
 if len(classes)<2:raise ValueError('Training requires at least two observed activity classes')
 unseen={m['label'] for m in metadata}-classes
 if unseen:raise ValueError('Training split lacks classes: '+', '.join(sorted(unseen)))
 provenance={name:{m['source_sha256'] for m,use in zip(metadata,mask) if use} for name,mask in masks.items()}
 if any(provenance[a]&provenance[b] for a,b in (('train','validation'),('train','test'),('validation','test'))):raise ValueError('Original capture crosses a split')
 return masks
