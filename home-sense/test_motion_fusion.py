import unittest
from motion_fusion import motion_evidence
class FusionTests(unittest.TestCase):
 def test_fresh_agreement_stale_and_incomplete(self):
  c={'connected':True,'motion':{'enabled':True,'status':'motion'}}
  n={'connected':True,'radar_verified':True,'frames':[{'received_at':10,'preview_incomplete':True,'points':[{'velocity_cm_s':70}]}]}
  self.assertEqual(motion_evidence(c,n,11)['status'],'corroborated_motion')
  self.assertEqual(motion_evidence(c,n,13)['status'],'partial_evidence')
  n['frames'][0]['points']=[]
  self.assertIsNone(motion_evidence(c,n,11)['radar_motion'])
  n['frames'][0]['preview_incomplete']=False
  self.assertEqual(motion_evidence(c,n,11)['status'],'sources_disagree')
