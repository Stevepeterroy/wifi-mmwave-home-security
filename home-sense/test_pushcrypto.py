"""Real ephemeral encryption and VAPID signing, with HTTP replaced locally."""
import base64,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import requests,http_ece
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption
from webpush import WebPush
class CryptoTests(unittest.TestCase):
 def test_library_encrypts_payload_for_subscriber_without_network(self):
  with tempfile.TemporaryDirectory() as folder:
   signing=ec.generate_private_key(ec.SECP256R1());client=ec.generate_private_key(ec.SECP256R1());auth=os.urandom(16)
   path=Path(folder)/'test-key.pem';path.write_bytes(signing.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()));path.chmod(0o600)
   encode=lambda value:base64.urlsafe_b64encode(value).decode().rstrip('=')
   subscription={'endpoint':'https://fcm.googleapis.com/fcm/send/local-fixture','keys':{'auth':encode(auth),'p256dh':encode(client.public_key().public_bytes(Encoding.X962,PublicFormat.UncompressedPoint))}}
   payload={'title':'Local fixture reminder','body':'A synthetic encryption test'};response=requests.Response();response.status_code=201;response._content=b''
   environment={'HAVEN_VAPID_PRIVATE_KEY':str(path),'HAVEN_VAPID_PUBLIC_KEY':encode(signing.public_key().public_bytes(Encoding.X962,PublicFormat.UncompressedPoint)),'HAVEN_VAPID_SUBJECT':'mailto:fixture@example.test'}
   with patch.dict(os.environ,environment),patch('pywebpush.requests.post',return_value=response) as transport:
    self.assertEqual(WebPush().send(subscription,payload),201)
   transport.assert_called_once();kwargs=transport.call_args.kwargs;encrypted=kwargs['data'];headers=kwargs['headers']
   self.assertNotIn(payload['body'].encode(),encrypted);self.assertEqual(headers['content-encoding'],'aes128gcm');self.assertEqual(headers['Urgency'],'high');self.assertTrue(headers['Authorization'].startswith('vapid '))
   self.assertEqual(json.loads(http_ece.decrypt(encrypted,private_key=client,auth_secret=auth,version='aes128gcm')),payload)
if __name__=='__main__':unittest.main()
