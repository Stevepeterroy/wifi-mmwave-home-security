import unittest
from rules import AwayRule
class ActivityIntervalTests(unittest.TestCase):
 def test_group_resume_timeout_restart_and_bounded_recording(self):
  rule=AwayRule();home={'away':True,'dataSource':'live','modules':[{'id':'a','roomId':''}],'rooms':[],'events':[]}
  def step(t,motion=True,connected=True):
   frame={'sequence':int(t*100),'received_at':t,'reported_points':int(motion),'points':[{'velocity_cm_s':70}] if motion else []}
   result=rule.evaluate(home,{'connected':connected,'radar_verified':True,'last_frame':frame},t)
   if result:home['events']=[result]
   return result
  self.assertIsNone(step(100));self.assertIsNone(step(100.2))
  first=step(100.4);self.assertTrue(first['newEpisode'])
  self.assertIsNone(step(101,False));resumed=step(200);self.assertEqual(first['id'],resumed['id']);self.assertFalse(resumed['newEpisode'])
  rule=AwayRule() # persisted event survives a process restart
  self.assertEqual(step(201)['id'],first['id'])
  for t in range(202,400):step(t)
  self.assertEqual(len(home['events'][0]['samples']),120);self.assertTrue(home['events'][0]['recordingTruncated'])
  self.assertIsNone(step(638,False,False))
  closed=step(639,False,False);self.assertEqual(closed['status'],'closed');self.assertIn('presence unknown',closed['stopReason'])
 def test_disarming_closes_open_event(self):
  home={'away':False,'modules':[{'id':'a'}],'events':[{'id':'e','moduleId':'a','status':'open','lastMotionEpoch':100}]}
  self.assertEqual(AwayRule().evaluate(home,{},101)['stopReason'],'Away mode disabled')
