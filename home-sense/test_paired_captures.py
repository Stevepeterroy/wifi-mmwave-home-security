import unittest
from paired_captures import PairedCaptures
from test_activity_sessions import fixture
from test_csi_recordings import fixture_samples
class CaptureTests(unittest.TestCase):
 def test_freezes_completed_scan_across_ring_expiry_and_rejects_different_scan(self):
  _,nodes,_=fixture();node=nodes['fixture-module'];samples=fixture_samples();c=PairedCaptures()
  node['scan_running']=True;c.observe('m',node,samples)
  self.assertEqual(c.samples('m',node['frames'],[]),[])
  node['scan_running']=False;c.observe('m',node,samples)
  saved=c.samples('m',node['frames'],[]);self.assertTrue(saved)
  c.observe('m',node,[]);self.assertEqual(c.samples('m',node['frames'],[]),saved)
  saved[0]['iq'][0]=99;self.assertNotEqual(c.samples('m',node['frames'],[]),saved)
  node['frames'][-1]['received_at']+=10
  self.assertEqual(c.samples('m',node['frames'],[]),[])
