import json,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from esp_setup import EspSetup

class EspSetupTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  folder=self.root/'firmware/rd60_wifi';folder.mkdir(parents=True)
  # Valid CA from an isolated test certificate, never production credentials.
  cert=self.root/'ca.crt';key=self.root/'ca.key'
  subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=test'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
  self.values={'HAVEN_WIFI_SSID':'demo','HAVEN_WIFI_PASSWORD':'private-password','HAVEN_MODULE_ID':'m','HAVEN_DEVICE_TOKEN':'private-device-token','HAVEN_EXCHANGE_URL':'https://192.168.1.19:8769/api/wifi/exchange','HAVEN_ROOT_CA':cert.read_text()}
  (folder/'secrets.h').write_text(''.join('#define '+k+' '+json.dumps(v)+'\n' for k,v in self.values.items())+'#define HAVEN_CSI_ONLY 1\n')
  (folder/'rd60_wifi.ino').write_text('// fixture')
  self.service=EspSetup(self.root,lambda:[{'port':'/dev/test-esp','name':'fixture'}])
  self.service.tools=lambda:('arduino-cli','esptool')
 def tearDown(self):self.temp.cleanup()
 def test_status_never_returns_credentials(self):
  s=self.service.status();encoded=json.dumps(s)
  self.assertNotIn('private-password',encoded);self.assertNotIn('private-device-token',encoded);self.assertTrue(s['hasPassword'])
 def test_settings_keep_password_only_for_same_network(self):
  self.service.save({'ssid':'demo','password':'','host':'192.168.1.19'})
  self.assertEqual(self.service.settings()['HAVEN_WIFI_PASSWORD'],'private-password')
  with self.assertRaises(ValueError):self.service.save({'ssid':'different','password':'','host':'192.168.1.19'})
  self.service.save({'ssid':'different','password':'','openNetwork':True,'host':'192.168.1.19'})
  self.assertEqual(self.service.settings()['HAVEN_WIFI_PASSWORD'],'')
  self.assertEqual((self.root/'firmware/rd60_wifi/secrets.h').stat().st_mode & 0o777,0o600)
 def test_invalid_input_never_changes_header(self):
  original=(self.root/'firmware/rd60_wifi/secrets.h').read_bytes()
  for body in ({'ssid':'demo','password':'short','host':'192.168.1.19'},{'ssid':'demo','password':'validpassword','host':'127.0.0.1'},{'ssid':'x\n','password':'validpassword','host':'192.168.1.19'}):
   with self.assertRaises(ValueError):self.service.save(body)
  self.assertEqual((self.root/'firmware/rd60_wifi/secrets.h').read_bytes(),original)
 def test_start_requires_confirmation_real_port_and_no_reader(self):
  for body,occupied in [({'port':'/dev/test-esp'},()),({'port':'/tmp/arbitrary','confirm':True},()),({'port':'/dev/test-esp','confirm':True},('/dev/test-esp',))]:
   with self.assertRaises(ValueError):self.service.start(body,occupied)
  with patch('esp_setup.threading.Thread') as thread:
   self.service.start({'port':'/dev/test-esp','confirm':True});thread.return_value.start.assert_called_once()
   with self.assertRaises(ValueError):self.service.start({'port':'/dev/test-esp','confirm':True})
 def test_combined_mode_requires_wiring_confirmation(self):
  with self.assertRaises(ValueError):self.service.start({'port':'/dev/test-esp','confirm':True,'mode':'csi_radar'})
  with self.assertRaises(ValueError):self.service.start({'port':'/dev/test-esp','confirm':True,'mode':'arbitrary','wiringConfirmed':True})
  with patch('esp_setup.threading.Thread'):
   job=self.service.start({'port':'/dev/test-esp','confirm':True,'mode':'csi_radar','wiringConfirmed':True})
   self.assertEqual(job['mode'],'csi_radar')
 def run_job(self,size,mode="csi_only"):
  calls=[]
  def runner(args,**kwargs):
   calls.append(args)
   if 'read-flash' in args:Path(args[-1]).write_bytes(b'\xff'*size)
  self.service.runner=runner
  job={'mode':mode,'id':'testjob','state':'running','phase':'Preparing','port':'/dev/test-esp','backupVerified':False}
  self.service.run(job,'arduino-cli','esptool');return job,calls
 def test_no_upload_after_short_backup(self):
  job,calls=self.run_job(12);self.assertEqual(job['state'],'failed');self.assertFalse(any('upload' in c for c in calls))
 def test_full_backup_precedes_upload(self):
  job,calls=self.run_job(0x400000);self.assertEqual(job['state'],'complete');self.assertTrue(job['backupVerified'])
  self.assertEqual([c[1] for c in calls if c[0]=='arduino-cli'],['compile','upload'])
  self.assertTrue((self.root/'data/esp-flash/testjob/backup.sha256').exists())
 def test_combined_build_enables_radar_without_changing_saved_network_settings(self):
  job,calls=self.run_job(0x400000,'csi_radar')
  built=(self.root/'data/esp-flash/testjob/rd60_wifi/secrets.h').read_text()
  self.assertIn('#define HAVEN_CSI_ONLY 0',built)
  self.assertIn('#define HAVEN_CSI_ONLY 1',(self.root/'firmware/rd60_wifi/secrets.h').read_text())
  self.assertEqual(job['state'],'complete')
 def test_changed_host_rotates_trust_and_preserves_csi_mode(self):
  result=self.service.save({'ssid':'new','password':'new-password','host':'192.168.5.2'})
  self.assertTrue(result['endpointChanged']);self.assertIn('192.168.5.2',self.service.settings()['HAVEN_EXCHANGE_URL'])
  self.assertIn('#define HAVEN_CSI_ONLY 1',(self.root/'firmware/rd60_wifi/secrets.h').read_text())

class EspSetupHttpTests(unittest.TestCase):
 def test_setup_requires_signed_in_loopback_and_rejects_cross_origin(self):
  import server,threading,urllib.request,urllib.error
  from http.server import ThreadingHTTPServer
  from unittest.mock import Mock
  auth=Mock();auth.enrolled=True;auth.authenticated.return_value=False
  service=Mock();service.status.return_value={'hasPassword':True};service.start.return_value={'state':'running'}
  with patch.multiple(server,AUTH=auth,ESP_SETUP=service):
   http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
   def req(body=None,origin=None):
    headers={'Host':'127.0.0.1:8768','Content-Type':'application/json'}
    if origin:headers['Origin']=origin
    return urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+'/api/esp/setup',data=json.dumps(body).encode() if body is not None else None,headers=headers))
   try:
    with self.assertRaises(urllib.error.HTTPError) as error:req()
    self.assertEqual(error.exception.code,401);service.status.assert_not_called()
    auth.authenticated.return_value=True
    self.assertEqual(json.load(req()),{'hasPassword':True})
    with self.assertRaises(urllib.error.HTTPError) as error:req({'ssid':'x'},'https://malicious.example')
    self.assertEqual(error.exception.code,403);service.save.assert_not_called()
   finally:http.shutdown();http.server_close()
 def test_non_loopback_cannot_read_settings(self):
  import server,threading,urllib.request,urllib.error
  from http.server import ThreadingHTTPServer
  from unittest.mock import Mock
  class RemoteHandler(server.Handler):
   def do_GET(self):
    self.client_address=('192.168.1.50',self.client_address[1]);return super().do_GET()
  auth=Mock();auth.enrolled=True;auth.authenticated.return_value=True;service=Mock()
  with patch.multiple(server,AUTH=auth,ESP_SETUP=service):
   http=ThreadingHTTPServer(('127.0.0.1',0),RemoteHandler);threading.Thread(target=http.serve_forever,daemon=True).start()
   try:
    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(http.server_port)+'/api/esp/setup',headers={'Host':'127.0.0.1:8768'}))
    self.assertEqual(error.exception.code,403);service.status.assert_not_called()
   finally:http.shutdown();http.server_close()

class FlashProgressTests(unittest.TestCase):
 def test_reports_percentage_elapsed_and_stall_without_leaking_logs(self):
  import os
  with tempfile.TemporaryDirectory() as tmp:
   service=EspSetup(Path(tmp),lambda:[])
   folder=Path(tmp)/'data/esp-flash/job';folder.mkdir(parents=True)
   log=folder/'backing.log';log.write_text('private-password\nReading [==] 84.7% 3551232/4194304 bytes...\rReading [==] 85.3% 3575808/4194304 bytes...')
   os.utime(log,(190,190))
   service.job={'id':'job','phase':'Backing up ESP32-S3 flash','state':'running','startedAt':100,'phaseStartedAt':110}
   with patch('esp_setup.time.time',return_value=200):status=service.job_status()
   self.assertEqual(status['progressPercent'],85.3);self.assertEqual(status['elapsedSeconds'],100);self.assertFalse(status['stalled'])
   self.assertNotIn('private-password',json.dumps(status))
   with patch('esp_setup.time.time',return_value=240):self.assertTrue(service.job_status()['stalled'])
 def test_terminal_elapsed_does_not_keep_increasing(self):
  service=EspSetup(Path('/tmp'),lambda:[]);service.job={'id':'fixture','phase':'Firmware installed','state':'complete','startedAt':100,'phaseStartedAt':110,'finishedAt':200}
  with patch('esp_setup.time.time',return_value=500):
   self.assertEqual(service.job_status()['elapsedSeconds'],100);self.assertEqual(service.job_status()['progressPercent'],100)

class PersistedFlashResultTests(unittest.TestCase):
 def test_interrupted_job_distinguishes_complete_backup_from_verified_upload(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'data/esp-flash/job';folder.mkdir(parents=True)
   result=folder.parent/'latest-result.json'
   base={'id':'job','state':'running','phase':'Backing up ESP32-S3 flash','ownerPid':99999999,'startedAt':100,'phaseStartedAt':110,'backupVerified':False}
   result.write_text(json.dumps(base))
   (folder/'before-first4MiB.bin').write_bytes(b'\xff'*0x400000)
   (folder/'backing.log').write_text('Read 4194304 bytes from 0x00000000 in 375.8 seconds')
   with patch('esp_setup.os.kill',side_effect=ProcessLookupError):
    interrupted=EspSetup(root,lambda:[])
   self.assertEqual(interrupted.job['state'],'failed')
   self.assertTrue(interrupted.job['backupVerified'])
   self.assertIn('upload not started',interrupted.job['phase'])
   self.assertEqual(json.loads(result.read_text())['state'],'failed')
   result.write_text(json.dumps({**base,'phase':'Uploading and verifying firmware'}))
   (folder/'uploading.log').write_text('Writing...\nHash of data verified.\n')
   with patch('esp_setup.os.kill',side_effect=ProcessLookupError):
    verified=EspSetup(root,lambda:[])
   self.assertEqual(verified.job['state'],'complete')
   self.assertEqual(json.loads(result.read_text())['state'],'complete')
 def test_completed_result_is_restored_but_running_result_is_not_claimed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'data/esp-flash/latest-result.json';p.parent.mkdir(parents=True)
   p.write_text(json.dumps({'id':'fixture','state':'complete','phase':'Firmware installed','startedAt':100,'finishedAt':200}))
   restored=EspSetup(root,lambda:[]);self.assertEqual(restored.job_status()['state'],'complete');self.assertEqual(restored.job_status()['elapsedSeconds'],100)
   p.write_text(json.dumps({'id':'fixture','state':'running'}));self.assertIsNone(EspSetup(root,lambda:[]).job)
