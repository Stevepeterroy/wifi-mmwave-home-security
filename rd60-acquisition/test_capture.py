"""Offline preservation tests; these do not validate radar hardware/protocol."""
import hashlib
import json
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from capture import record_stream

class FakePort:
    def __init__(self, stop, parts, fail=False):
        self.stop, self.parts, self.fail = stop, list(parts), fail
    @property
    def in_waiting(self):
        return len(self.parts[0]) if self.parts else 0
    def read(self, n):
        if self.parts:
            return self.parts.pop(0)
        if self.fail:
            raise IOError('simulated disconnect')
        self.stop.set()
        return b''

class CaptureTests(unittest.TestCase):
    def run_capture(self, parts, fail=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            stop=threading.Event(); errors=queue.Queue(); stats={}
            record_stream(FakePort(stop, parts, fail), root, 'uart1', stop, errors, stats)
            return ((root/'uart1.bin').read_bytes(),
                    [json.loads(s) for s in (root/'uart1.chunks.jsonl').read_text().splitlines()], stats, errors)
    def test_binary_and_offsets(self):
        parts=[b'\x00\xff\r\n', bytes(range(256)), b'last']
        data, index, stats, errors=self.run_capture(parts)
        self.assertEqual(data,b''.join(parts))
        self.assertEqual([r['offset'] for r in index],[0,4,260])
        self.assertEqual([r['length'] for r in index],[4,256,4])
        self.assertEqual(stats['uart1']['sha256'],hashlib.sha256(data).hexdigest())
        self.assertTrue(errors.empty())
    def test_empty_is_preserved(self):
        data, index, stats, errors=self.run_capture([])
        self.assertEqual(data,b''); self.assertEqual(index,[])
        self.assertEqual(stats['uart1']['bytes'],0)
    def test_disconnect_keeps_partial_bytes_and_error(self):
        data, index, stats, errors=self.run_capture([b'partial'],True)
        self.assertEqual(data,b'partial')
        self.assertIn('simulated disconnect',errors.get_nowait())
        self.assertEqual(stats['uart1']['bytes'],7)

if __name__=='__main__':
    unittest.main()
