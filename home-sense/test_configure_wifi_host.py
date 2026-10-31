import importlib.util
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parent/'tools'))
from configure_wifi_host import provision
from check_wifi_settings import read_settings, validate

class ConfigureHostTests(unittest.TestCase):
 def test_rejects_unreachable_hosts(self):
  for host in ('127.0.0.1','0.0.0.0','8.8.8.8','224.0.0.1','not-a-host'):
   with self.assertRaises(ValueError):provision(host)
 def test_preserves_credentials_and_backs_up(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);header=root/'firmware/rd60_wifi/secrets.h';header.parent.mkdir(parents=True)
   original='\n'.join('#define '+k+' "'+v+'"' for k,v in {
    'HAVEN_WIFI_SSID':'test-network','HAVEN_WIFI_PASSWORD':'test-password',
    'HAVEN_MODULE_ID':'node-1','HAVEN_DEVICE_TOKEN':'private-token',
    'HAVEN_EXCHANGE_URL':'https://192.168.1.2:8769/api/wifi/exchange',
    'HAVEN_ROOT_CA':''}.items())
   header.write_text(original)
   provision('192.168.1.19',root)
   settings=read_settings(header.read_text())
   self.assertEqual(settings['HAVEN_DEVICE_TOKEN'],'private-token')
   self.assertEqual(settings['HAVEN_WIFI_PASSWORD'],'test-password')
   self.assertEqual(settings['HAVEN_EXCHANGE_URL'],'https://192.168.1.19:8769/api/wifi/exchange')
   self.assertEqual(validate(settings),[])
   self.assertEqual(next((root/'data/device-tls').glob('backup-*/secrets.h')).read_text(),original)
   self.assertEqual(header.stat().st_mode & 0o777,0o600)

if __name__=='__main__':unittest.main()
