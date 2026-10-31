import unittest
from wifi_discovery import DeviceDiscovery
class Keys:
 def issue(self,module):return 'private-'+module
class DiscoveryTests(unittest.TestCase):
 def test_approval_is_delivered_only_to_original_requester(self):
  clock=[0];d=DeviceDiscovery(lambda:clock[0]);body={'deviceId':'AABBCCDDEEFF','requestSecret':'a'*32}
  self.assertEqual(d.announce(body),{'pending':True})
  self.assertNotIn('secret',str(d.list()))
  d.approve(body['deviceId'],'module',Keys())
  self.assertNotIn('private-',str(d.list()))
  with self.assertRaises(ValueError):d.announce({**body,'requestSecret':'b'*32})
  self.assertEqual(d.announce(body)['deviceToken'],'private-module')
  other={'deviceId':'112233445566','requestSecret':'b'*32}
  d.announce(other)
  with self.assertRaises(ValueError):d.approve(other['deviceId'],'module',Keys())
  clock[0]=61;self.assertEqual(d.list(),[])
  with self.assertRaises(ValueError):d.approve(body['deviceId'],'module',Keys())
 def test_invalid_identity_and_bounded_queue(self):
  d=DeviceDiscovery()
  with self.assertRaises(ValueError):d.announce({'deviceId':'bad','requestSecret':'a'*32})
  for i in range(32):d.announce({'deviceId':f'{i:012x}','requestSecret':'a'*32})
  with self.assertRaises(ValueError):d.announce({'deviceId':'ffffffffffff','requestSecret':'a'*32})
