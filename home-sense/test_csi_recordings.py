"""Synthetic capture tests; never annotate uncontrolled hardware recordings."""
import copy,unittest
from csi_recordings import attach,quality,digest
from test_activity_sessions import capture
from activity_sessions import quality as session_quality

def fixture_samples():
 return [{'sequence':i+1,'device_ms':i*50,'age_ms':0,'received_at':1000+i*.05,
  'rssi':-50,'channel':5,'boot':'fixture-only','first_word_invalid':True,'iq':[10,0]*64} for i in range(80)]

class CsiRecordingTests(unittest.TestCase):
 def test_overlap_integrity_and_legacy(self):
  original=capture();self.assertFalse(quality(original)['available'])
  cap=attach(original,fixture_samples())
  self.assertTrue(quality(cap)['paired']);self.assertLess(len(cap['csi_samples']),80)
  cap['csi_samples'][0]['iq'][5]=11
  with self.assertRaisesRegex(ValueError,'integrity'):session_quality(cap)
 def test_missing_restart_and_nonfinite(self):
  cap=attach(capture(),[{**s,'received_at':s['received_at']+100} for s in fixture_samples()])
  self.assertFalse(quality(cap)['paired']);self.assertEqual(cap['csi_samples'],[])
  cap=attach(capture(),fixture_samples());cap['csi_samples'][-1]['boot']='restart';cap['csi_sha256']=digest(cap['csi_samples'])
  self.assertFalse(quality(cap)['ordered'])
  cap['csi_samples'][0]['received_at']=float('inf')
  with self.assertRaises(ValueError):digest(cap['csi_samples'])
