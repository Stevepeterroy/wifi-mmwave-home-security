#!/usr/bin/env python3
"""Preserve RD-60 serial bytes. No packet decoding or completeness claims."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import threading
import time


def record_stream(port, folder, name, stop, errors, stats):
    digest = hashlib.sha256()
    count = 0
    chunks = 0
    try:
        with (folder / (name + '.bin')).open('xb') as raw, (folder / (name + '.chunks.jsonl')).open('x') as index:
            while not stop.is_set():
                data = port.read(max(1, min(port.in_waiting, 16384)))
                stamp = time.monotonic_ns()
                if not data:
                    continue
                raw.write(data)
                index.write(json.dumps({'chunk': chunks, 'offset': count, 'length': len(data), 'host_receive_monotonic_ns': stamp}) + '\n')
                digest.update(data)
                count += len(data)
                chunks += 1
    except Exception as exc:
        errors.put(name + ': ' + repr(exc))
        stop.set()
    finally:
        stats[name] = {'bytes': count, 'chunks': chunks, 'sha256': digest.hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--list', action='store_true', help='List serial ports; do not open them')
    p.add_argument('--control', help='Radar UART0 port')
    p.add_argument('--data', help='Radar UART1 port')
    p.add_argument('--seconds', type=float, default=30)
    p.add_argument('--out', type=Path)
    p.add_argument('--data-baud', type=int, default=1000000)
    p.add_argument('--data-rtscts', action='store_true', help='Test hardware flow control; not a verified requirement')
    p.add_argument('--commands', type=Path, help='Explicitly send commands from this file to UART0')
    p.add_argument('--stop-after', action='store_true', help='Send mmwc stop at cleanup; useful with --commands')
    p.add_argument('--note', default='', help='Module, DIP settings, activity, session, and other context')
    args = p.parse_args()
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        p.exit(2, 'Install dependency first: python -m pip install pyserial==3.5\n')
    if args.list:
        for port in list_ports.comports():
            print(port.device, port.description, port.hwid)
        return 0
    if not args.control or not args.data or not args.out:
        p.error('--control, --data and --out are required')
    if args.control == args.data:
        p.error('Control and data must be different ports')
    if not 0 < args.seconds < 86400 or args.data_baud <= 0:
        p.error('Duration must be positive and under one day; baud must be positive')
    commands = []
    if args.commands:
        commands = [s.strip() for s in args.commands.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')]
        for command in commands:
            command.encode('ascii')
            if not command.startswith('mmwc '):
                p.error('Command file must contain only mmwc commands and # comments')
    args.out.mkdir(parents=True, exist_ok=False)
    metadata = {'started_utc': datetime.now(timezone.utc).isoformat(), 'start_monotonic_ns': time.monotonic_ns(),
                'control_port': args.control, 'control_baud': 115200, 'data_port': args.data,
                'data_baud': args.data_baud, 'data_rtscts': args.data_rtscts,
                'format': '8N1', 'note': args.note, 'commands': commands, 'requested_seconds_after_commands': args.seconds,
                'timestamp_meaning': 'Host read completion for chunks, not radar frame/sample times',
                'packet_loss': 'Unknown: this recorder does not parse device frame IDs or expose driver overrun counters'}
    stop = threading.Event()
    errors = queue.Queue()
    stats = {}
    threads = []
    status = 'incomplete'
    def save():
        (args.out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    save()
    try:
        with ExitStack() as stack:
            ports = []
            for name, baud, flow in [(args.control, 115200, False), (args.data, args.data_baud, args.data_rtscts)]:
                port = serial.Serial(port=None, baudrate=baud, timeout=0.05, write_timeout=1,
                                     rtscts=flow, xonxoff=False, dsrdtr=False)
                port.dtr = False
                port.rts = True  # Assert host ready when software-controlled; driver owns it with RTS/CTS.
                port.port = name
                port.open()
                stack.callback(port.close)
                ports.append(port)
            eventlog = stack.enter_context((args.out / 'commands.jsonl').open('x'))
            def send(command):
                payload = (command + '\r\n').encode('ascii')
                eventlog.write(json.dumps({'command': command, 'send_monotonic_ns': time.monotonic_ns()}) + '\n')
                eventlog.flush()
                if ports[0].write(payload) != len(payload):
                    raise IOError('Incomplete command write')
            for name, port in zip(('uart0', 'uart1'), ports):
                t = threading.Thread(target=record_stream, args=(port, args.out, name, stop, errors, stats))
                t.start()
                threads.append(t)
            try:
                for command in commands:
                    if stop.is_set():
                        raise IOError('Reader failed during command sequence')
                    send(command)
                    stop.wait(0.25)
                # Commands are logged, not semantically validated. Review UART0 before accepting a session.
                stop.wait(args.seconds)
                status = 'captured' if errors.empty() else 'failed'
            except KeyboardInterrupt:
                status = 'interrupted'
            finally:
                if args.stop_after:
                    try:
                        send('mmwc stop')
                        time.sleep(0.3)
                    except Exception as exc:
                        errors.put('Stop command: ' + repr(exc))
                stop.set()
                for t in threads:
                    t.join()
    except Exception as exc:
        errors.put(repr(exc))
        status = 'failed'
    finally:
        stop.set()
        for t in threads:
            t.join()
        failures = []
        while not errors.empty():
            failures.append(errors.get())
        if failures:
            status = 'failed'
        metadata.update(status=status, streams=stats, errors=failures, ended_utc=datetime.now(timezone.utc).isoformat())
        save()
    print(json.dumps({'status': status, 'streams': stats, 'errors': failures}, indent=2))
    if not stats.get('uart1', {}).get('bytes'):
        print('UART1 EMPTY: no usable radar data captured.')
        return 2
    print('Bytes captured; full frames, valid coordinates, and zero loss are NOT yet verified.')
    return 0 if status == 'captured' else 1

if __name__ == '__main__':
    raise SystemExit(main())
