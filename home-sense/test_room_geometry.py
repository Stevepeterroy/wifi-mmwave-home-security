import unittest
from room_geometry import validate_boundary,contains_point,reflection_in_room
from rules import AwayRule
class RoomGeometryTests(unittest.TestCase):
 def setUp(self):
  self.room={'id':'r','name':'L-shaped','x':0,'z':0,'width':3,'depth':3,'boundary':[{'x':0,'z':0},{'x':3,'z':0},{'x':3,'z':1},{'x':1,'z':1},{'x':1,'z':3},{'x':0,'z':3}]}
 def test_concave_and_mounted_coordinate_membership(self):
  validate_boundary(self.room)
  self.assertTrue(contains_point({'x':.5,'z':2},self.room));self.assertFalse(contains_point({'x':2,'z':2},self.room))
  self.assertTrue(reflection_in_room({'x_cm':200,'y_cm':50},{'x':0,'z':0,'yaw':90},self.room)==False)
 def test_invalid_points_and_crossing(self):
  for boundary in [[{'x':0,'z':0}]*3,[{'x':0,'z':0},{'x':3,'z':3},{'x':0,'z':3},{'x':3,'z':0}],[{'x':0,'z':0},{'x':float('nan'),'z':1},{'x':1,'z':0}]]:
   with self.assertRaises(ValueError):validate_boundary({**self.room,'boundary':boundary})
 def test_away_ignores_reflections_outside_polygon(self):
  home={'away':True,'dataSource':'live','rooms':[self.room],'activeModuleId':'m','modules':[{'id':'m','roomId':'r','x':0,'z':0,'yaw':0}]};rule=AwayRule()
  for i in range(1,5):
   state={'connected':True,'radar_verified':True,'last_frame':{'sequence':i,'received_at':100+i*.2,'reported_points':1,'points':[{'x_cm':200,'y_cm':200,'velocity_cm_s':70}]}}
   self.assertIsNone(rule.evaluate(home,state,100+i*.2))
  for i in range(5,8):
   state['last_frame'].update(sequence=i,received_at=100+i*.2,points=[{'x_cm':50,'y_cm':200,'velocity_cm_s':70}]);event=rule.evaluate(home,state,100+i*.2)
  self.assertEqual(event['room'],'L-shaped')
