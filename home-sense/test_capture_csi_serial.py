import unittest
import contextlib
import io
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

from capture_csi_serial import decode_sample, main


class SerialCsiTests(unittest.TestCase):
    def record(self):
        return {'type': 'csi', 'boot': 'observed-boot', 'sequence': 1,
                'device_ms': 50, 'rssi': -48, 'channel': 6,
                'first_word_invalid': True, 'iq_hex': '807fff00' * 32}

    def test_lossless_signed_iq_and_timestamps(self):
        result = decode_sample(self.record(), 123.5)
        self.assertEqual(result['iq'], [-128, 127, -1, 0] * 32)
        self.assertEqual(result['received_at'], 123.5)
        self.assertEqual(result['device_ms'], 50)
        self.assertTrue(result['first_word_invalid'])

    def test_diagnostics_are_not_samples(self):
        self.assertIsNone(decode_sample({'type': 'status', 'samples': 20}, 1))
        self.assertIsNone(decode_sample({'type': 'ready'}, 1))

    def test_usb_disconnect_preserves_timestamped_partial_capture(self):
        record=self.record()
        class BrokenSerial:
            def __enter__(self):self.reads=0;return self
            def __exit__(self,*args):return False
            def read(self,size):
                self.reads+=1
                if self.reads==1:return (json.dumps(record)+'\n').encode()
                raise OSError('device disconnected')
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'partial'
            with patch.dict(sys.modules,{'serial':types.SimpleNamespace(Serial=BrokenSerial)}), patch.object(sys,'argv',[
                'capture','--port','test-port','--seconds','30','--output',str(out)]), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:main()
            self.assertEqual(raised.exception.code,3)
            bundle=json.loads((out/'capture.json').read_text())
            self.assertFalse(bundle['summary']['capture_complete'])
            self.assertEqual(len(bundle['samples']),1)
            journal=json.loads((out/'samples.jsonl').read_text())
            self.assertEqual(journal,bundle['samples'][0])
            self.assertIsInstance(journal['received_at'],float)
            self.assertEqual(json.loads((out/'start.json').read_text())['port'],'test-port')

    def test_malformed_records_are_rejected(self):
        for change in [{'iq_hex': '00' * 127}, {'iq_hex': 'gg' * 128},
                       {'sequence': True}, {'device_ms': -1}, {'rssi': 1},
                       {'channel': 0}, {'first_word_invalid': 1}, {'boot': ''}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                decode_sample(self.record() | change, 1)


if __name__ == '__main__':
    unittest.main()
