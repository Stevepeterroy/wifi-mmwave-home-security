"""Finite raw CSI USB capture. Labels remain unverified operator observations."""
import argparse
import datetime
import hashlib
import json
import time
from pathlib import Path


def decode_sample(record, received_at):
    if record.get('type') != 'csi':
        return None
    for field, lo, hi in [('sequence', 1, 2**32-1), ('device_ms', 0, 2**32-1),
                          ('rssi', -128, 0), ('channel', 1, 14)]:
        if type(record.get(field)) is not int or not lo <= record[field] <= hi:
            raise ValueError('Invalid ' + field)
    if not isinstance(record.get('boot'), str) or not record['boot']:
        raise ValueError('Missing boot identity')
    if type(record.get('first_word_invalid')) is not bool:
        raise ValueError('Invalid first word flag')
    encoded = record.get('iq_hex')
    if not isinstance(encoded, str) or len(encoded) != 256:
        raise ValueError('Expected 128 IQ bytes as hex')
    raw = bytes.fromhex(encoded)
    if len(raw) != 128:
        raise ValueError('Invalid hex encoding')
    return {k: record[k] for k in ('boot', 'sequence', 'device_ms', 'rssi', 'channel', 'first_word_invalid')} | {
        'iq': [b if b < 128 else b-256 for b in raw], 'received_at': received_at}


def main():
    import serial
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', required=True)
    p.add_argument('--baud', type=int, default=115200)
    p.add_argument('--seconds', type=float, default=30)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not 0 < args.seconds <= 3600:
        raise ValueError('Capture must be between zero and one hour')
    args.output.mkdir(parents=True, exist_ok=False)
    samples = []; diagnostics = []; errors = 0
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    capture_error = None
    began = time.monotonic()
    (args.output/'start.json').write_text(json.dumps({'started_at':started,
        'port':args.port,'baud':args.baud,'requested_seconds':args.seconds})+'\n')
    # Preserve every serial byte, including boot text and malformed records.
    with (args.output/'serial.log').open('wb') as raw, (args.output/'samples.jsonl').open('w') as journal:
        connection = serial.Serial()
        connection.port = args.port; connection.baudrate = args.baud
        connection.timeout = .25; connection.dtr = False; connection.rts = False
        try:
            with connection:
                deadline = time.monotonic() + args.seconds
                pending = bytearray()
                while time.monotonic() < deadline:
                    chunk = connection.read(4096)
                    raw.write(chunk); raw.flush(); pending.extend(chunk)
                    while b'\n' in pending:
                        line, _, pending = pending.partition(b'\n')
                        try:
                            record = json.loads(line)
                            if not isinstance(record, dict):
                                raise ValueError('Expected object')
                            sample = decode_sample(record, time.time())
                            if sample is None:
                                diagnostics.append(record)
                            else:
                                samples.append(sample)
                                journal.write(json.dumps(sample,separators=(',',':'))+'\n')
                        except (ValueError, UnicodeDecodeError):
                            errors += 1
                    journal.flush()
                    if len(pending) > 16384:
                        pending.clear(); errors += 1
        except (OSError, KeyboardInterrupt) as exc:
            capture_error = {'type':type(exc).__name__,'message':str(exc)}
    pairs = [(a,b) for a,b in zip(samples, samples[1:]) if a['boot'] == b['boot']]
    intervals = [b['device_ms']-a['device_ms'] for a,b in pairs]
    lost = sum(max(0,b['sequence']-a['sequence']-1) for a,b in pairs)
    summary = {'started_at': started, 'port': args.port, 'baud': args.baud,
               'requested_seconds': args.seconds, 'samples': len(samples),
               'actual_seconds': time.monotonic()-began,
               'capture_complete': capture_error is None, 'capture_error':capture_error,
               'boot_ids': sorted({s['boot'] for s in samples}),
               'channels': sorted({s['channel'] for s in samples}),
               'missing_sequences': lost,
               'sequence_reversals_or_duplicates': sum(b['sequence'] <= a['sequence'] for a,b in pairs),
               'nonpositive_device_intervals': sum(v <= 0 for v in intervals),
               'max_device_gap_ms': max(intervals) if intervals else None,
               'device_rate_hz': 1000*len(intervals)/sum(intervals) if intervals and all(v>0 for v in intervals) else None,
               'rssi_range_dbm': [min(s['rssi'] for s in samples),max(s['rssi'] for s in samples)] if samples else None,
               'unparsed_lines': errors, 'diagnostics': diagnostics,
               'serial_sha256': hashlib.sha256((args.output/'serial.log').read_bytes()).hexdigest()}
    bundle = {'source': 'HAVEN_CSI_USB_v1 router LLTF', 'label': 'unlabelled',
              'timing': 'Device milliseconds; received_at is host batch receipt, not acquisition synchronization.',
              'samples': samples, 'summary': summary}
    (args.output/'capture.json').write_text(json.dumps(bundle, separators=(',', ':'))+'\n')
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2), flush=True)
    if capture_error:
        raise SystemExit(3)
    if not samples:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
