import tempfile,unittest
from pathlib import Path
from wifi_discovery import DeviceDiscovery
from wifi_transport import DeviceKeys,WifiBridge,PollSerial,LINK_TIMEOUT_SECONDS
from wifi_inventory import inventory
class InventoryTests(unittest.TestCase):
 def test_pending_connected_offline_paused_and_secret_redaction(self):
  with tempfile.TemporaryDirectory() as folder:
   keys=DeviceKeys(lambda:Path(folder)/'test.db');discovery=DeviceDiscovery();bridge=WifiBridge()
   home={'modules':[{'id':'a','name':'Radar A'},{'id':'b','name':'Radar B'}]}
   discovery.announce({'deviceId':'112233AABBCC','requestSecret':'a'*32})
   rows=inventory(discovery,keys,bridge,home);self.assertEqual(rows[0]['status'],'available');self.assertNotIn('secret',str(rows))
   discovery.approve('112233AABBCC','a',keys)
   keys.issue('b') # older pairings do not have a known physical MAC
   clock=[10];channel=PollSerial('a'*16,now=lambda:clock[0]);bridge.channels['a']=channel
   rows=inventory(discovery,keys,bridge,home)
   self.assertEqual(rows[0]['status'],'connected');self.assertEqual(rows[0]['deviceId'],'112233AABBCC');self.assertEqual(rows[1]['status'],'offline')
   self.assertNotIn('deviceToken',str(rows));self.assertNotIn('requestSecret',str(rows))
   clock[0]=14;self.assertEqual(inventory(discovery,keys,bridge,home)[0]['status'],'connected')
   clock[0]=10+LINK_TIMEOUT_SECONDS+1;self.assertEqual(inventory(discovery,keys,bridge,home)[0]['status'],'offline')
   bridge.paused.add('a');self.assertEqual(inventory(discovery,keys,bridge,home)[0]['status'],'paused')
   self.assertEqual(DeviceKeys(lambda:Path(folder)/'test.db').bindings(),{'a':'112233AABBCC'})
   keys.forget('a','112233AABBCC')
   discovery.forget('112233AABBCC')
   bridge.disconnect('a')
   self.assertFalse(keys.has_key('a'))
   self.assertEqual(keys.bindings(),{})
   self.assertEqual(discovery.list(),[])
   self.assertEqual([r['moduleId'] for r in inventory(discovery,keys,bridge,home)],['b'])
