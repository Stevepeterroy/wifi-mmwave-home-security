"""Provision a private LAN TLS endpoint. Existing Wi-Fi credentials are preserved."""
import argparse
import getpass
import ipaddress
import json
import os
import re
from pathlib import Path
import shutil
import secrets
import subprocess
import tempfile
from datetime import datetime
try:
    from .check_wifi_settings import read_settings
except ImportError:
    from check_wifi_settings import read_settings

ROOT = Path(__file__).resolve().parents[1]

def provision(host, root=ROOT, network=None):
    address = ipaddress.ip_address(host)
    if address.version != 4 or not address.is_private or address.is_loopback or address.is_unspecified or address.is_multicast:
        raise ValueError('Use the laptop private LAN IP reachable by the ESP')
    header = root / 'firmware/rd60_wifi/secrets.h'
    source = header.read_text()
    settings = read_settings(source)
    if network is not None:
        ssid, password = network
        if not ssid or len(ssid.encode()) > 32 or (password and not 8 <= len(password) <= 63):
            raise ValueError('Use a nonempty SSID (up to 32 bytes) and an 8–63 character password, or blank for an open network')
        settings['HAVEN_WIFI_SSID'], settings['HAVEN_WIFI_PASSWORD'] = ssid, password
    folder = root / 'data/device-tls'
    folder.mkdir(parents=True, exist_ok=True)
    backup = folder / ('backup-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(mode=0o700)
    for path in (header, folder/'server.crt', folder/'server.key', folder/'host.env'):
        if path.exists():
            target = backup/path.name
            shutil.copy2(path, target)
            target.chmod(0o600)
    with tempfile.TemporaryDirectory(dir=folder) as temp:
        temp = Path(temp)
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes',
            '-keyout',str(temp/'server.key'),'-out',str(temp/'server.crt'),
            '-days','365','-subj','/CN=Haven LAN device endpoint',
            '-addext',f'subjectAltName=IP:{address}',
            '-addext','basicConstraints=critical,CA:TRUE'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        settings['HAVEN_EXCHANGE_URL'] = f'https://{address}:8769/api/wifi/exchange'
        settings['HAVEN_ROOT_CA'] = (temp/'server.crt').read_text()
        # Preserve SSID/password and pairing values without displaying them.
        content = '#pragma once\n// Private generated settings. Never commit.\n'
        for key, value in settings.items():
            content += '#define ' + key + ' ' + json.dumps(value) + '\n'
        mode = re.search(r'^#define HAVEN_CSI_ONLY [01]$', source, re.M)
        if mode: content += mode[0] + '\n'
        time_key = secrets.token_hex(32)
        content += '#define HAVEN_TIME_HOST ' + json.dumps(str(address)) + '\n'
        content += '#define HAVEN_TIME_KEY ' + json.dumps(time_key) + '\n'
        (temp/'secrets.h').write_text(content)
        for name in ('server.key','server.crt'):
            (temp/name).chmod(0o600)
            os.replace(temp/name,folder/name)
        (temp/'secrets.h').chmod(0o600)
        os.replace(temp/'secrets.h',header)
    env = folder/'host.env'
    env.write_text(f'HAVEN_ALLOWED_HOSTS={address}:8769\nHAVEN_LOCAL_TIME_BIND={address}\nHAVEN_LOCAL_TIME_KEY={time_key}\n')
    env.chmod(0o600)
    return str(address)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True,help='Current laptop private LAN IP')
    parser.add_argument('--network',action='store_true',help='Prompt privately for a different router SSID/password')
    args = parser.parse_args()
    network = None
    if args.network:
        network = (input('2.4 GHz Wi-Fi name: ').strip(), getpass.getpass('Wi-Fi password (hidden): '))
    try:
        print('Configured verified TLS for LAN host',provision(args.host, network=network))
        print('Restart Haven and rebuild/upload the ESP firmware. Old settings are privately backed up.')
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        raise SystemExit('Configuration failed: '+str(exc))
