"""CSI provenance and timing quality for operator-annotated recordings."""
import hashlib,json,math

def digest(samples):
 return hashlib.sha256(json.dumps(samples,sort_keys=True,allow_nan=False).encode()).hexdigest()

def estimated_received_time(sample):
 return sample['received_at']-sample['age_ms']/1000

def quality(capture):
 samples=capture.get('csi_samples')
 if samples is None:return {'samples':0,'available':False,'ordered':False,'paired':False}
 if not isinstance(samples,list) or len(samples)>2000:raise ValueError('Invalid recorded CSI count')
 if capture.get('csi_source')!='ESP32-S3 router LLTF CSI':raise ValueError('Invalid recorded CSI provenance')
 if capture.get('csi_sha256')!=digest(samples):raise ValueError('Recorded CSI integrity check failed')
 for s in samples:
  if not isinstance(s,dict):raise ValueError('Invalid recorded CSI sample')
  for field,lo,hi in [('sequence',1,2**32-1),('device_ms',0,2**32-1),('age_ms',0,1000),('rssi',-128,0),('channel',1,14)]:
   if type(s.get(field)) is not int or not lo<=s[field]<=hi:raise ValueError('Invalid recorded CSI '+field)
  if not isinstance(s.get('boot'),str) or not s['boot'] or len(s['boot'])>64:raise ValueError('Invalid recorded CSI boot')
  if type(s.get('received_at')) not in (int,float) or not math.isfinite(s['received_at']):raise ValueError('Invalid recorded CSI receipt time')
  if type(s.get('first_word_invalid')) is not bool:raise ValueError('Invalid recorded CSI flag')
  iq=s.get('iq')
  if not isinstance(iq,list) or len(iq)!=128 or any(type(v) is not int or not -128<=v<=127 for v in iq):raise ValueError('Invalid recorded CSI IQ')
 if not samples:return {'samples':0,'available':False,'ordered':False,'paired':False}
 single=len({s['boot'] for s in samples})==1 and len({s['channel'] for s in samples})==1
 ordered=single and all(a['device_ms']<b['device_ms'] and a['sequence']<b['sequence'] and a['received_at']<=b['received_at'] for a,b in zip(samples,samples[1:]))
 device_gaps=[(b['device_ms']-a['device_ms'])/1000 for a,b in zip(samples,samples[1:])] if ordered else []
 host_times=[estimated_received_time(s) for s in samples]
 frames=capture.get('frames',[]);radar_times=[f.get('received_at') for f in frames]
 radar_valid=radar_times and all(type(t) in (int,float) and math.isfinite(t) for t in radar_times)
 overlap=max(0,min(max(host_times),max(radar_times))-max(min(host_times),min(radar_times))) if radar_valid else 0
 return {'samples':len(samples),'available':True,'ordered':ordered,'single_boot_and_channel':single,
  'duration_seconds':(samples[-1]['device_ms']-samples[0]['device_ms'])/1000 if ordered else None,
  'max_device_gap_seconds':max(device_gaps) if device_gaps else None,
  'sequence_gaps':sum(b['sequence']-a['sequence']-1 for a,b in zip(samples,samples[1:])) if ordered else None,
  'host_overlap_seconds':overlap,'paired':bool(ordered and overlap>=2),
  'timing_basis':'CSI host receipt minus queued age; radar host receipt. Acquisition synchronization unverified.'}

def attach(capture,samples):
 frames=capture['frames'];times=[f.get('received_at') for f in frames]
 valid=times and all(type(t) in (int,float) and math.isfinite(t) for t in times)
 chosen=[s for s in samples if min(times)-.4<=estimated_received_time(s)<=max(times)+.4] if valid else []
 capture.update(csi_samples=chosen,csi_source='ESP32-S3 router LLTF CSI',csi_sha256=digest(chosen),
  csi_timing='CSI device clock retained; estimated host time is receipt minus queued age. Not acquisition-synchronized.')
 capture['limitations']=[v for v in capture['limitations'] if v!='No CSI or vital signs']+['No vital signs','CSI/radar acquisition synchronization unverified']
 quality(capture)
 return capture
