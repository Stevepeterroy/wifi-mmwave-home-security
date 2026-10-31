import base64,json,tempfile,threading,time,unittest,urllib.request,urllib.error,ssl
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from wifi_transport import DeviceKeys,PollSerial,WifiBridge,LINK_TIMEOUT_SECONDS

def packet(seq=0,data=b'',boot='0123456789abcdef',age=0):
 return {'moduleId':'m','sequence':seq,'boot':boot,'age_ms':age,'data':base64.b64encode(data).decode()}

class TransportTests(unittest.TestCase):
 def test_explicit_pause_blocks_automatic_recovery_until_reset(self):
  from unittest.mock import Mock
  registry=Mock();bridge=WifiBridge();bridge.exchange('m',packet(),registry)
  bridge.disconnect('m',pause=True)
  with self.assertRaisesRegex(ValueError,'paused'):bridge.exchange('m',packet(boot='abcdef0123456789'),registry)
  bridge.disconnect('m');bridge.exchange('m',packet(boot='abcdef0123456789'),registry)
  self.assertEqual(registry.connect_wifi.call_count,2)
 def test_fresh_boot_recovers_expired_channel_but_never_live_channel(self):
  class Registry:
   def __init__(self):self.stream=None
   def connect_wifi(self,module,stream):self.stream=stream
  registry=Registry();bridge=WifiBridge();bridge.exchange('m',packet(),registry)
  old=registry.stream;newboot='abcdef0123456789'
  with self.assertRaises(ValueError):bridge.exchange('m',packet(boot=newboot),registry)
  old.close()
  with self.assertRaises(ValueError):bridge.exchange('m',packet(seq=9,boot=newboot),registry)
  bridge.exchange('m',packet(boot=newboot),registry)
  self.assertIsNot(registry.stream,old);self.assertEqual(registry.stream.boot,newboot)
  registry.stream.close()
  with self.assertRaises(ValueError):bridge.exchange('m',packet(boot=old.boot),registry)
 def test_retry_does_not_duplicate_bytes_or_lose_commands(self):
  stream=PollSerial('0123456789abcdef');stream.write(b'INFO\n')
  first=stream.exchange(packet(data=b'hello\n'));self.assertEqual(first['commands'],['INFO'])
  self.assertEqual(stream.exchange(packet(data=b'hello\n')),first)
  self.assertEqual(stream.read(100),b'hello\n');self.assertEqual(stream.in_waiting,0)
  with self.assertRaises(ValueError):stream.exchange(packet(data=b'different'))
  with self.assertRaises(ValueError):stream.exchange(packet(seq=2))
  with self.assertRaises(ValueError):stream.exchange(packet(seq=1,boot='fedcba9876543210'))
 def test_stale_and_overflow_fail_closed(self):
  clock=[0];stream=PollSerial('0123456789abcdef',lambda:clock[0])
  with self.assertRaises(ValueError):stream.exchange(packet(age=1001))
  for i in range(8):stream.exchange(packet(i,b'x'*8192))
  with self.assertRaises(ValueError):stream.exchange(packet(8,b'x'))
  with self.assertRaises(OSError):stream.read(1)
  clock[0]=0;fresh=PollSerial('0123456789abcdef',lambda:clock[0]);fresh.exchange(packet())
  clock[0]=4;self.assertEqual(fresh.exchange(packet()),{'accepted':0,'commands':[]})
  clock[0]=LINK_TIMEOUT_SECONDS+5
  with self.assertRaises(OSError):fresh.write(b'INFO\n')
  with self.assertRaises(ValueError):fresh.exchange(packet())
 def test_module_credentials_persist_rotate_and_revoke(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'keys.sqlite3';store=DeviceKeys(lambda:path);token=store.issue('m')
   self.assertTrue(DeviceKeys(lambda:path).verify('m',token));self.assertFalse(store.verify('other',token))
   replacement=store.issue('m');self.assertFalse(store.verify('m',token));self.assertTrue(store.verify('m',replacement))
   store.revoke('m');self.assertFalse(store.verify('m',replacement))
   self.assertNotIn(token,path.read_bytes().decode(errors='ignore'))
 def test_module_streams_and_commands_are_isolated(self):
  class Registry:
   def __init__(self):self.streams={}
   def connect_wifi(self,module,stream):self.streams[module]=stream
  registry=Registry();bridge=WifiBridge()
  bridge.exchange('a',packet(data=b'a-log'),registry);bridge.exchange('b',packet(data=b'b-log'),registry)
  registry.streams['a'].write(b'INFO\n');registry.streams['b'].write(b'STATUS\n')
  self.assertEqual(bridge.exchange('a',packet(1),registry)['commands'],['INFO'])
  self.assertEqual(bridge.exchange('b',packet(1),registry)['commands'],['STATUS'])
  self.assertEqual(registry.streams['a'].read(99),b'a-log');self.assertEqual(registry.streams['b'].read(99),b'b-log')
  bridge.disconnect('a');self.assertFalse(registry.streams['b'].closed)
 def test_invalid_bootstrap_cannot_open_a_reader_and_commands_are_bounded(self):
  from unittest.mock import Mock
  registry=Mock();bridge=WifiBridge()
  for body in (packet(seq=1),packet(age=1001),{**packet(),'data':'%%%'},{**packet(),'boot':'invalid'}):
   with self.assertRaises(ValueError):bridge.exchange('m',body,registry)
  registry.connect_wifi.assert_not_called();self.assertFalse(bridge.channels)
  stream=PollSerial('0123456789abcdef')
  for cmd in (b'\n',b'INFO\nSTATUS',b'x'*129):
   with self.assertRaises(ValueError):stream.write(cmd)
  for _ in range(32):stream.write(b'INFO\n')
  with self.assertRaises(OSError):stream.write(b'INFO\n')
 def test_reader_verifies_through_poll_transport_and_disconnects(self):
  from nodes import NodeRegistry
  registry=NodeRegistry();bridge=WifiBridge();seq=0;incoming=b'';halt=threading.Event()
  bridge.exchange('m',packet(),registry);seq=1
  def peer():
   nonlocal seq,incoming
   while not halt.is_set():
    try:response=bridge.exchange('m',packet(seq,incoming),registry)
    except ValueError:return
    seq+=1;incoming=b''
    for command in response['commands']:
     reply={'INFO':'[INFO] ready=1 control=RX16/TX17/115200 data=RX21/1000000',
      'CONTROL_MATRIX':'[CONTROL_MATRIX]','PIN_FIX':'[PIN_FIX] result=0',
      'mmwc version':'[RADAR] MMW version:V4.130.4.2\n[RADAR] <Success 0>'}.get(command,'[RADAR] <Success 0>')
     incoming+=(reply+'\n').encode()
    # Include a poll delay; the network path must not inherit short USB waits.
    time.sleep(.15)
  worker=threading.Thread(target=peer,daemon=True);worker.start()
  try:
   deadline=time.monotonic()+15
   while not registry.snapshot()['m']['radar_verified'] and time.monotonic()<deadline:time.sleep(.05)
   state=registry.snapshot()['m'];self.assertTrue(state['radar_verified']);self.assertEqual(state['version'],'V4.130.4.2');self.assertEqual(state['transport'],'wifi')
   bridge.disconnect('m');registry.get('m').WORKER.join(2)
   self.assertFalse(registry.snapshot()['m']['connected'])
  finally:halt.set();bridge.disconnect('m');registry.shutdown();worker.join(1)

class WifiHttpTests(unittest.TestCase):
 def test_local_reset_unpauses_existing_sensor_without_creating_keys(self):
  import server
  from auth import Auth
  from nodes import NodeRegistry
  with tempfile.TemporaryDirectory() as folder:
   auth=Auth(Path(folder)/'fixture.sqlite3');bridge=WifiBridge();registry=NodeRegistry();bridge.disconnect('m',pause=True)
   with patch.multiple(server,AUTH=auth,WIFI=bridge,NODES=registry),patch.object(server,'get_config',return_value={'modules':[{'id':'m'}]}):
    http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
    def request(route):
     return urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+route,data=b'{"moduleId":"m"}',headers={'Host':'127.0.0.1:8768','Content-Type':'application/json'}))
    try:
     self.assertTrue(json.load(request('/api/wifi/reset'))['reset']);self.assertNotIn('m',bridge.paused)
     with self.assertRaises(urllib.error.HTTPError):request('/api/wifi/pair')
    finally:http.shutdown();http.server_close()
 def test_token_scope_authentication_and_reader_ownership(self):
  import server
  from auth import Auth
  from nodes import NodeRegistry
  from database import connection
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'http.sqlite3'
   with connection(path) as db:db.execute('CREATE TABLE config (id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
   auth=Auth(path);auth.setup('test-wifi-only-password')
   keys=DeviceKeys(lambda:path);token=keys.issue('m');registry=NodeRegistry();bridge=WifiBridge()
   cfg={'rooms':[],'modules':[{'id':'m'}]}
   with patch.multiple(server,DB=path,AUTH=auth,DEVICE_KEYS=keys,NODES=registry,WIFI=bridge),patch.object(server,'get_config',return_value=cfg):
    http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
    def request(route,body=None,key=token):
     return urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+route,data=json.dumps(body).encode() if body is not None else None,headers={'Host':'127.0.0.1:8768','Authorization':'Bearer '+key,'Content-Type':'application/json'}))
    try:
     with self.assertRaises(urllib.error.HTTPError) as pairing:request('/api/wifi/pair',{'moduleId':'m'})
     self.assertEqual(pairing.exception.code,401)
     with self.assertRaises(urllib.error.HTTPError) as denied:request('/api/wifi/exchange',packet(),key='wrong')
     self.assertEqual(denied.exception.code,401);self.assertFalse(bridge.channels)
     with self.assertRaises(urllib.error.HTTPError) as browser:request('/api/home')
     self.assertEqual(browser.exception.code,401)
     response=json.load(request('/api/wifi/exchange',packet()));self.assertEqual(response['accepted'],0)
     self.assertEqual(registry.get('m').STATE['transport'],'wifi')
     with self.assertRaises(urllib.error.HTTPError) as scope:request('/api/wifi/exchange',{**packet(),'moduleId':'other'})
     self.assertEqual(scope.exception.code,401)
     with self.assertRaises(ValueError):registry.connect_wifi('m',PollSerial('fedcba9876543210'))
    finally:
     bridge.disconnect('m');registry.shutdown();registry.get('m').WORKER.join(2);http.shutdown();http.server_close()

 def test_non_loopback_requires_verified_tls(self):
  import server
  from auth import Auth
  from nodes import NodeRegistry
  from cryptography import x509
  from cryptography.hazmat.primitives import hashes,serialization
  from cryptography.hazmat.primitives.asymmetric import rsa
  from cryptography.x509.oid import NameOID
  class RemoteHandler(server.Handler):
   def setup(self):
    super().setup();self.client_address=('192.0.2.10',self.client_address[1])
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'tls.sqlite3';auth=Auth(path);auth.setup('test-https-only-password')
   keys=DeviceKeys(lambda:path);token=keys.issue('m');registry=NodeRegistry();bridge=WifiBridge()
   private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
   name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')]);now=datetime.now(timezone.utc)
   cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(private.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).sign(private,hashes.SHA256())
   certfile=Path(folder)/'cert.pem';keyfile=Path(folder)/'key.pem'
   certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM));keyfile.write_bytes(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
   server_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server_context.load_cert_chain(certfile,keyfile)
   # Trust only this test certificate, with normal hostname verification enabled.
   client_context=ssl.create_default_context(cafile=str(certfile))
   with patch.multiple(server,DB=path,AUTH=auth,DEVICE_KEYS=keys,NODES=registry,WIFI=bridge),patch.object(server,'get_config',return_value={'modules':[{'id':'m'}]}):
    plain=ThreadingHTTPServer(('127.0.0.1',0),RemoteHandler)
    secure=ThreadingHTTPServer(('127.0.0.1',0),RemoteHandler);secure.socket=server_context.wrap_socket(secure.socket,server_side=True)
    for service in (plain,secure):threading.Thread(target=service.serve_forever,daemon=True).start()
    def send(service,scheme):
     req=urllib.request.Request(f'{scheme}://localhost:{service.server_port}/api/wifi/exchange',data=json.dumps(packet()).encode(),headers={'Host':'localhost:8768','Authorization':'Bearer '+token})
     return urllib.request.urlopen(req,context=client_context)
    try:
     with self.assertRaises(urllib.error.HTTPError) as denied:send(plain,'http')
     self.assertEqual(denied.exception.code,403);self.assertFalse(bridge.channels)
     self.assertEqual(json.load(send(secure,'https'))['accepted'],0)
    finally:
     bridge.disconnect('m');registry.shutdown();registry.get('m').WORKER.join(2)
     for service in (plain,secure):service.shutdown();service.server_close()

if __name__=='__main__':unittest.main()

class CsiOnlyTransportTests(unittest.TestCase):
 def test_csi_only_does_not_open_or_verify_radar(self):
  from unittest.mock import Mock
  registry=Mock();bridge=WifiBridge()
  for i in range(20):
   response=bridge.exchange('m',{**packet(i),'sensor_mode':'csi_only'},registry)
   self.assertEqual(response,{'accepted':i,'commands':[]})
  registry.connect_wifi.assert_not_called()
  bridge.disconnect('m',pause=True)
  with self.assertRaises(ValueError):bridge.exchange('m',{**packet(),'sensor_mode':'csi_only'},registry)
 def test_modes_are_explicit_and_cannot_smuggle_radar_bytes(self):
  from unittest.mock import Mock
  bridge=WifiBridge();registry=Mock()
  with self.assertRaises(ValueError):bridge.exchange('m',{**packet(data=b'fake'),'sensor_mode':'csi_only'},registry)
  bridge.exchange('m',{**packet(),'sensor_mode':'csi_only'},registry)
  with self.assertRaises(ValueError):bridge.exchange('m',packet(1),registry)
