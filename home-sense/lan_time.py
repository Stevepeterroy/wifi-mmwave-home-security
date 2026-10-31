"""Authenticated, local-only clock bootstrap for ESP TLS on offline routers."""
import hashlib
import hmac
import socket
import time


def serve(host: str, key_hex: str, port: int = 8767):
    key = bytes.fromhex(key_hex)
    if len(key) != 32:
        raise ValueError('LAN time key must contain 32 bytes')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((host, port))
        while True:
            packet, peer = sock.recvfrom(64)
            if len(packet) != 11 or not packet.startswith(b'HT1'):
                continue
            message = packet + int(time.time()).to_bytes(8, 'big')
            sock.sendto(message + hmac.new(key, message, hashlib.sha256).digest(), peer)
