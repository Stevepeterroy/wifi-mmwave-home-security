"""Create an explicitly annotated session from an exported console preview.
Labels describe the operator's session annotation, never model predictions.
"""
import argparse,json,hashlib,copy
from pathlib import Path
LABELS={'unlabelled','empty-room','walking','standing','sitting','lying-down'}
def session(capture,session_id,subject_id,label,room_id):
 if capture.get('source')!='live ESP console preview':raise ValueError('Use a live console-preview export; recorded replay cannot establish a new labelled experiment')
 if label not in LABELS:raise ValueError('Unsupported session label')
 if not all(isinstance(v,str) and v.strip() for v in (session_id,subject_id,room_id)):raise ValueError('Session, participant and room identifiers are required')
 frames=capture.get('frames')
 if not isinstance(frames,list) or not frames:raise ValueError('Export has no frames')
 for frame in frames:
  if not isinstance(frame,dict) or not isinstance(frame.get('points'),list):raise ValueError('Invalid preview frame')
 return {'schema':'haven-annotated-preview-v1','session_id':session_id,'participant_id':subject_id,'room_id':room_id,'annotation':{'label':label,'basis':'operator-provided whole-session annotation','verified':False},'source':capture['source'],'module_id':capture.get('moduleId'),'firmware':capture.get('version'),'complete_binary_cloud':False,'timing':'Host receipt timestamps when present; not radar acquisition timestamps','limitations':['Console previews may omit points','No CSI or vital signs','Whole-session labels require review; mixed activities should be separate sessions'],'frames':frames}
def annotated_snapshot(home,nodes,body):
 if not isinstance(body,dict):raise ValueError('Expected session metadata')
 module_id=body.get('moduleId');module=next((m for m in home.get('modules',[]) if m.get('id')==module_id),None)
 if not module:raise ValueError('Choose a registered module')
 assigned_room=module.get('roomId') if isinstance(module.get('roomId'),str) and module['roomId'].strip() else 'unassigned'
 selected_room=body.get('roomId')
 if selected_room is not None:
  if not isinstance(selected_room,str) or not any(r.get('id')==selected_room for r in home.get('rooms',[])):raise ValueError('Choose a valid room for this session')
 room_id=selected_room if selected_room is not None else assigned_room
 node=nodes.get(module_id)
 if not node or not node.get('radar_verified'):raise ValueError('Verify the radar before annotating a session')
 if node.get('scan_pending') or node.get('scan_running') or node.get('monitoring'):raise ValueError('Stop monitoring and finish the finite scan before annotating')
 if node.get('scan_error') or node.get('stop_acknowledged') is not True:raise ValueError('Resolve the scan or stop acknowledgment before annotating')
 capture={'source':'live ESP console preview','moduleId':module_id,'version':node.get('version'),'frames':node.get('frames',[])}
 result=session(capture,body.get('sessionId'),body.get('participantId'),body.get('label'),room_id)
 result['room_assignment_verified']=room_id!='unassigned' and room_id==assigned_room
 result['placement']=copy.deepcopy(module)
 room=next((r for r in home.get('rooms',[]) if r.get('id')==room_id),None)
 result['room_geometry']=copy.deepcopy(room) if room else None
 result['home_model_id']=home.get('homeModelId')
 result['physical_calibration_verified']=False
 result['source_sha256']=hashlib.sha256(json.dumps(capture,sort_keys=True,allow_nan=False).encode()).hexdigest()
 result['source_hash_basis']='Canonical JSON live snapshot, sorted keys'
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('output',type=Path);p.add_argument('--session',required=True);p.add_argument('--participant',required=True,help='Pseudonymous participant ID; use a separate ID for empty-room sessions');p.add_argument('--room',required=True);p.add_argument('--label',choices=sorted(LABELS),default='unlabelled');a=p.parse_args()
 raw=a.capture.read_bytes();value=session(json.loads(raw),a.session,a.participant,a.label,a.room);value['source_sha256']=hashlib.sha256(raw).hexdigest()
 with a.output.open('x') as output:json.dump(value,output,indent=2)
 a.output.chmod(0o600)
 print('Saved annotated preview session. Split by participant/session before training; labels are not verified detections.')
if __name__=='__main__':main()
