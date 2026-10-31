import unittest,tempfile,json
from models import ModelStore
class DeleteTests(unittest.TestCase):
 def test_archive_and_protect(self):
  with tempfile.TemporaryDirectory() as root:
   store=ModelStore(root);folder=store.folder('scan');folder.mkdir();(folder/'manifest.json').write_text('{}');(folder/'0.blob').write_bytes(b'data')
   for config in ({'homeModelId':'scan'},):
    with self.assertRaises(ValueError):store.delete('scan',config)
    self.assertTrue(folder.exists())
   store.delete('scan',{})
   self.assertFalse(folder.exists());self.assertEqual(store.deleted_ids(),['scan']);self.assertEqual(store.list(),[])
   self.assertEqual((store.root/'.deleted'/'scan'/'0.blob').read_bytes(),b'data')
 def test_invalid_path(self):
  with tempfile.TemporaryDirectory() as root:
   with self.assertRaises(ValueError):ModelStore(root).delete('../outside',{})
