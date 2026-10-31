import base64,unittest
from radar_bytes import RadarBytes

def chunk(seq=1,data=b'\x00\xff\x48'):
 return {'sequence':seq,'device_ms':100,'age_ms':1,'data':base64.b64encode(data).decode()}
class RadarByteTests(unittest.TestCase):
 def test_raw_bytes_are_retained_without_claiming_decoded_frames(self):
  s=RadarBytes();s.ingest('m','boot',[chunk()]);s.ingest('m','boot',[chunk()])
  self.assertEqual(s.summary('m')['bytes'],3);self.assertFalse(s.summary('m')['complete_point_cloud'])
  self.assertEqual(base64.b64decode(s.export('m')['chunks'][0]['data']),b'\x00\xff\x48')
 def test_bounded_retention_boot_changes_and_module_isolation(self):
  s=RadarBytes()
  for i in range(1,201):s.ingest('m','boot',[chunk(i,b'x'*512)])
  self.assertEqual(s.summary('m')['retained_bytes'],65536);self.assertEqual(s.summary('other')['bytes'],0)
  s.ingest('m','new',[chunk()]);self.assertEqual(s.summary('m')['bytes'],3)
 def test_validation_gap_and_drop_reporting(self):
  s=RadarBytes()
  for value in ([{**chunk(),'data':'!'}],[chunk(data=b'')],[chunk(data=b'x'*513)],[{**chunk(),'age_ms':1001}]):
   with self.assertRaises(ValueError):s.ingest('m','boot',value)
  s.ingest('m','boot',[chunk(3)],7);self.assertEqual(s.summary('m')['sequence_gaps'],2);self.assertEqual(s.summary('m')['dropped_bytes'],7)

class RadarByteHttpTests(unittest.TestCase):
 def test_authenticated_device_delivery_and_workspace_export(self):
  import server,tempfile,threading,json,urllib.request
  from pathlib import Path
  from unittest.mock import patch,Mock
  from http.server import ThreadingHTTPServer
  from auth import Auth
  from wifi_transport import DeviceKeys,WifiBridge
  from csi_stream import CsiStreams
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'fixture.sqlite3';auth=Auth(db);cookie=auth.setup('isolated-fixture-password');keys=DeviceKeys(lambda:db);key=keys.issue('m')
   registry=Mock();registry.snapshot.return_value={};raw=RadarBytes();cfg={'activeModuleId':'m','modules':[{'id':'m'}]}
   with patch.multiple(server,AUTH=auth,DEVICE_KEYS=keys,WIFI=WifiBridge(),NODES=registry,RADAR_BYTES=raw,CSI=CsiStreams(),PAIRED_CAPTURES=Mock()),patch.object(server,'get_config',return_value=cfg):
    http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
    base='http://127.0.0.1:'+str(http.server_port)
    try:
     body={'moduleId':'m','boot':'0123456789abcdef','sequence':0,'age_ms':0,'data':'','sensor_mode':'radar','radar_uart':[chunk()],'radar_dropped_bytes':0,'csi':[]}
     req=urllib.request.Request(base+'/api/wifi/exchange',data=json.dumps(body).encode(),headers={'Host':'127.0.0.1:8768','Authorization':'Bearer '+key,'Content-Type':'application/json'})
     self.assertEqual(json.load(urllib.request.urlopen(req))['accepted'],0)
     req=urllib.request.Request(base+'/api/radar/raw',headers={'Host':'127.0.0.1:8768','Cookie':'haven_session='+cookie})
     exported=json.load(urllib.request.urlopen(req));self.assertEqual(exported['summary']['bytes'],3);self.assertFalse(exported['summary']['decoded'])
    finally:http.shutdown();http.server_close()
