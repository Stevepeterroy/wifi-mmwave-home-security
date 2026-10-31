import tempfile,unittest,base64
from pathlib import Path
from cryptography.hazmat.primitives.serialization import load_pem_private_key,Encoding,PublicFormat
from configure_push import generate
class KeyTests(unittest.TestCase):
 def test_matching_public_key_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as folder:
   files=generate(folder,'mailto:fixture@example.test');key=load_pem_private_key(files[0].read_bytes(),password=None);public=files[1].read_bytes()
   self.assertEqual(base64.urlsafe_b64decode(public+b'='*(-len(public)%4)),key.public_key().public_bytes(Encoding.X962,PublicFormat.UncompressedPoint));self.assertEqual(files[0].stat().st_mode&0o777,0o600)
   before=files[0].read_bytes()
   with self.assertRaises(ValueError):generate(folder,'mailto:other@example.test')
   self.assertEqual(files[0].read_bytes(),before)
 def test_requires_contact_uri(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaises(ValueError):generate(folder,'not-a-contact')
   self.assertEqual(list(Path(folder).iterdir()),[])
if __name__=='__main__':unittest.main()
