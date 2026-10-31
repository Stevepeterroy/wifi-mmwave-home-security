"""Read-only pre-upload validation. Never print private setting values."""
import argparse
import ast
import ipaddress
import re
import ssl
from pathlib import Path
from urllib.parse import urlsplit

FIELDS = ('HAVEN_WIFI_SSID', 'HAVEN_WIFI_PASSWORD', 'HAVEN_MODULE_ID',
          'HAVEN_DEVICE_TOKEN', 'HAVEN_EXCHANGE_URL', 'HAVEN_ROOT_CA')

def read_settings(source):
    settings = {}
    for field in FIELDS:
        match = re.search(r'^\s*#define\s+' + field + r'\s+(R"([^\s()]*)\((.*?)\)\2"|"(?:\\.|[^"\\])*")', source, re.M | re.S)
        if not match:
            raise ValueError('Use a quoted string or raw string literal for ' + field)
        if match.group(2) is not None:
            settings[field] = match.group(3)
        else:
            try:
                settings[field] = ast.literal_eval(match.group(1))
            except (SyntaxError, ValueError):
                raise ValueError('Invalid quoted string for ' + field) from None
    return settings

def validate(settings):
    errors = []
    for field in FIELDS:
        if field not in ('HAVEN_WIFI_PASSWORD', 'HAVEN_DEVICE_TOKEN', 'HAVEN_MODULE_ID') and not settings[field].strip():
            errors.append(field + ' is missing')
    if len(settings['HAVEN_WIFI_SSID'].encode()) > 32:
        errors.append('Wi-Fi name exceeds 32 bytes')
    try:
        url = urlsplit(settings['HAVEN_EXCHANGE_URL'])
        host = url.hostname or ''
        _ = url.port
        if url.scheme != 'https' or not host or url.path != '/api/wifi/exchange' or url.query or url.fragment or url.username or url.password:
            errors.append('Use an HTTPS server URL ending in /api/wifi/exchange without credentials or query parameters')
        loopback = host.lower() == 'localhost'
        try:
            address = ipaddress.ip_address(host)
            loopback |= address.is_loopback or address.is_unspecified
        except ValueError:
            pass
        if loopback or host == 'your-haven-host':
            errors.append('The server address must reach the laptop from the ESP; replace localhost or the example hostname')
    except ValueError:
        errors.append('Invalid server URL')
    try:
        ssl.create_default_context(cadata=settings['HAVEN_ROOT_CA'])
    except (ssl.SSLError, ValueError):
        errors.append('Provide a parseable PEM CA certificate for the server')
    return errors

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('header', nargs='?', default='firmware/rd60_wifi/secrets.h')
    args = parser.parse_args()
    try:
        errors = validate(read_settings(Path(args.header).read_text()))
    except FileNotFoundError:
        errors = ['Private settings file is missing; copy secrets.example.h to secrets.h and configure it locally']
    except ValueError as exc:
        errors = [str(exc)]
    for error in errors:
        print('Needs setup: ' + error)
    if not errors:
        print('Settings syntax and CA certificate parse correctly. Network reachability, certificate hostname, pairing authorization and hardware operation still require real-device testing.')
    raise SystemExit(bool(errors))
