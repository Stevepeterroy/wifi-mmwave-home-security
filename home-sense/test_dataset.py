import unittest
from dataset import session
class DatasetTests(unittest.TestCase):
 def test_preserves_partial_data_and_annotation_provenance(self):
  frames=[{'sequence':1,'reported_points':9,'preview_incomplete':True,'points':[{'x_cm':1}]}]
  result=session({'source':'live ESP console preview','moduleId':'m1','frames':frames},'s1','p1','walking','r1')
  self.assertEqual(result['frames'],frames);self.assertFalse(result['annotation']['verified']);self.assertFalse(result['complete_binary_cloud']);self.assertEqual(result['annotation']['basis'],'operator-provided whole-session annotation')
 def test_refuses_replay_empty_capture_and_unsubstantiated_labels(self):
  for capture,label in [({'source':'recorded','frames':[{}]},'walking'),({'source':'live ESP console preview','frames':[]},'walking'),({'source':'live ESP console preview','frames':[{'points':[]}]},'fall')]:
   with self.assertRaises(ValueError):session(capture,'s1','p1',label,'r1')
if __name__=='__main__':unittest.main()

class SnapshotTests(unittest.TestCase):
 def fixture(self):
  return ({'modules':[{'id':'m1','roomId':'r1','yaw':0}]},{'m1':{'radar_verified':True,'stop_acknowledged':True,'frames':[{'points':[],'reported_points':0}]}},{'moduleId':'m1','sessionId':'s1','participantId':'p1','label':'empty-room'})
 def test_export_binds_label_room_module_and_placement(self):
  from dataset import annotated_snapshot
  home,nodes,body=self.fixture();result=annotated_snapshot(home,nodes,body)
  self.assertEqual(result['module_id'],'m1');self.assertEqual(result['room_id'],'r1');self.assertEqual(result['placement']['yaw'],0);self.assertEqual(len(result['source_sha256']),64);self.assertFalse(result['annotation']['verified'])
 def test_requires_completed_acknowledged_session(self):
  from dataset import annotated_snapshot
  for state in [{'scan_running':True},{'scan_pending':True},{'monitoring':True},{'stop_acknowledged':False},{'scan_error':'fault'},{'radar_verified':False}]:
   home,nodes,body=self.fixture();nodes['m1'].update(state)
   with self.assertRaises(ValueError):annotated_snapshot(home,nodes,body)
 def test_unassigned_room_retains_unknown_placement(self):
  from dataset import annotated_snapshot
  home,nodes,body=self.fixture();home['modules'][0]['roomId']=''
  value=annotated_snapshot(home,nodes,body)
  self.assertEqual(value['room_id'],'unassigned');self.assertIsNone(value['room_geometry'])
  self.assertFalse(value['room_assignment_verified']);self.assertEqual(value['placement']['roomId'],'')
 def test_explicit_room_selection_preserves_provenance(self):
  from dataset import annotated_snapshot
  home,nodes,body=self.fixture();home['rooms']=[{'id':'r1','name':'Room one'},{'id':'r2','name':'Room two'}]
  body['roomId']='r2';value=annotated_snapshot(home,nodes,body)
  self.assertEqual(value['room_id'],'r2');self.assertEqual(value['room_geometry']['name'],'Room two')
  self.assertFalse(value['room_assignment_verified'])
  body['roomId']='r1';self.assertTrue(annotated_snapshot(home,nodes,body)['room_assignment_verified'])
  body['roomId']='unknown'
  with self.assertRaises(ValueError):annotated_snapshot(home,nodes,body)

class ScanPlacementProvenanceTests(unittest.TestCase):
 def test_saved_scan_placement_and_derived_room_geometry_survive_export(self):
  from dataset import annotated_snapshot
  room={'id':'scan:fixture','name':'Scanned space','x':0,'z':0,'width':3.32825779914856,'depth':4.307100772857666,'planModelId':'fixture','scanEnvelope':True}
  module={'id':'fixture-module','roomId':room['id'],'x':1.5,'z':2,'height':.5,'yaw':90,'planModelId':'fixture','scanAlignment':{'scale':1,'upAxis':'Y','yaw':0}}
  home={'rooms':[room],'modules':[module],'homeModelId':'fixture'}
  node={'radar_verified':True,'stop_acknowledged':True,'frames':[{'sequence':1,'reported_points':0,'points':[]}]}
  result=annotated_snapshot(home,{'fixture-module':node},{'moduleId':'fixture-module','sessionId':'fixture-session','participantId':'fixture-person','label':'unlabelled'})
  self.assertEqual(result['room_geometry'],room);self.assertEqual(result['placement']['scanAlignment'],module['scanAlignment']);self.assertEqual(result['home_model_id'],'fixture');self.assertFalse(result['physical_calibration_verified'])
  room['width']=99;module['x']=99;module['scanAlignment']['yaw']=99
  self.assertEqual(result['room_geometry']['width'],3.32825779914856);self.assertEqual(result['placement']['x'],1.5)
  self.assertEqual(result['placement']['scanAlignment']['yaw'],0)
