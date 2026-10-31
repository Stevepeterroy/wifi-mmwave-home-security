import unittest
from csi_stream import CsiStreams
class CsiTests(unittest.TestCase):
 def sample(self,seq=1):return {'sequence':seq,'device_ms':50,'age_ms':0,'rssi':-50,'channel':1,'first_word_invalid':True,'iq':[1,-2]*64}
 def test_retries_boots_and_export(self):
  c=CsiStreams();s=self.sample();c.ingest('m','a',[s]);c.ingest('m','a',[s]);self.assertEqual(c.summary('m')['samples'],1)
  self.assertFalse(c.summary('m')['detection_enabled']);c.ingest('m','b',[s]);self.assertEqual(len(c.export('m')),1);self.assertEqual(c.export('m')[0]['boot'],'b')
 def test_invalid_and_bounded(self):
  c=CsiStreams()
  for bad in ({**self.sample(),'iq':[0]*127},{**self.sample(),'age_ms':1001},{**self.sample(),'rssi':True}):
   with self.assertRaises(ValueError):c.ingest('m','a',[bad])
  for seq in range(1,2005):c.ingest('m','a',[self.sample(seq)])
  self.assertEqual(len(c.export('m')),2000)
