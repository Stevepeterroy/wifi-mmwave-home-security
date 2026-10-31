#!/usr/bin/env python3
"""
wifi_proxy.py — HTTP-aware proxy that forwards 0.0.0.0:8768 → 127.0.0.1:8768
Rewrites the Host header to '127.0.0.1:8768' so Haven accepts the request,
handles CORS preflight (OPTIONS) requests, and injects CORS headers into all responses.
"""
import socket, threading, sys, re, time

LOCAL_HOST  = "127.0.0.1"
BIND_HOST   = "0.0.0.0"
PORT        = 8768
TARGET_HOST = f"{LOCAL_HOST}:{PORT}"
BUF         = 65536
LOG_FILE    = "proxy.log"

CORS_HEADERS = (
    b"Access-Control-Allow-Origin: *\r\n"
    b"Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS, HEAD\r\n"
    b"Access-Control-Allow-Headers: *\r\n"
    b"Access-Control-Max-Age: 86400\r\n"
)

def log(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [proxy] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def rewrite_host(data: bytes) -> bytes:
    """Rewrite Host and Origin/Referer headers to match target 127.0.0.1:8768."""
    try:
        header_end = data.find(b"\r\n\r\n")
        sep_len = 4
        if header_end == -1:
            header_end = data.find(b"\n\n")
            sep_len = 2
        if header_end == -1:
            headers = data
            body = b""
        else:
            headers = data[:header_end]
            body = data[header_end + sep_len:]

        headers = re.sub(
            rb"(?i)(Host\s*:\s*)[^\r\n]+",
            rb"\g<1>" + TARGET_HOST.encode(),
            headers,
        )
        headers = re.sub(
            rb"(?i)(Origin\s*:\s*)[^\r\n]+",
            rb"\g<1>http://" + TARGET_HOST.encode(),
            headers,
        )
        headers = re.sub(
            rb"(?i)(Referer\s*:\s*https?://)[^/\r\n]+",
            rb"\g<1>" + TARGET_HOST.encode(),
            headers,
        )
        sep = b"\r\n\r\n" if sep_len == 4 else b"\n\n"
        return headers + sep + body
    except Exception:
        return data


def inject_cors(data: bytes) -> bytes:
    """Inject CORS headers into HTTP response bytes without altering the body."""
    try:
        header_end = data.find(b"\r\n\r\n")
        if header_end != -1:
            headers = data[:header_end]
            body = data[header_end + 4:]
            return headers + b"\r\n" + CORS_HEADERS + b"\r\n" + body
        header_end = data.find(b"\n\n")
        if header_end != -1:
            headers = data[:header_end]
            body = data[header_end + 2:]
            return headers + b"\n" + CORS_HEADERS + b"\n" + body
    except Exception:
        pass
    return data


def pipe_response(src: socket.socket, dst: socket.socket, client_ip: str):
    """Forward response from Haven to client, injecting CORS headers."""
    try:
        first = src.recv(BUF)
        if not first:
            return
        modified = inject_cors(first)
        dst.sendall(modified)
        status_line = first.split(b"\r\n")[0].decode(errors="ignore")
        log(f"Response to {client_ip}: {status_line}")
        while True:
            data = src.recv(BUF)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        for s in (src, dst):
            try: s.close()
            except Exception: pass


def pipe_request(src: socket.socket, dst: socket.socket):
    """Forward request body without modifying any bytes."""
    try:
        while True:
            data = src.recv(BUF)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        for s in (src, dst):
            try: s.close()
            except Exception: pass


def handle(client: socket.socket, addr):
    client_ip = f"{addr[0]}:{addr[1]}"
    try:
        client.settimeout(10.0)
        peek_data = client.recv(BUF)
        if not peek_data:
            client.close()
            return

        # Ensure complete headers are read
        while b"\r\n\r\n" not in peek_data and b"\n\n" not in peek_data and len(peek_data) < 65536:
            more = client.recv(4096)
            if not more:
                break
            peek_data += more

        first_line = peek_data.split(b"\r\n")[0].decode(errors="ignore")
        log(f"Incoming from {client_ip} -> {first_line}")

        # Check for CORS preflight OPTIONS request
        if peek_data.startswith(b"OPTIONS "):
            log(f"Handling OPTIONS preflight for {client_ip}")
            response = (
                b"HTTP/1.1 204 No Content\r\n"
                + CORS_HEADERS
                + b"Content-Length: 0\r\n"
                b"Connection: close\r\n\r\n"
            )
            client.sendall(response)
            client.close()
            return

        # Connect to backend Haven server
        try:
            backend = socket.create_connection((LOCAL_HOST, PORT), timeout=5)
        except Exception as exc:
            log(f"Cannot reach Haven on {LOCAL_HOST}:{PORT} — {exc}")
            client.close()
            return

        # Send the initial rewritten request chunk
        backend.sendall(rewrite_host(peek_data))

        # Forward remainder of request and response in threads
        client.settimeout(None)
        t_req = threading.Thread(target=pipe_request, args=(client, backend), daemon=True)
        t_resp = threading.Thread(target=pipe_response, args=(backend, client, client_ip), daemon=True)
        t_req.start()
        t_resp.start()

    except Exception as exc:
        log(f"Error handling connection from {client_ip}: {exc}")
        try: client.close()
        except Exception: pass


def get_wifi_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "<your-mac-ip>"


def main():
    ip = get_wifi_ip()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((BIND_HOST, PORT))
    except OSError as exc:
        log(f"Cannot bind {BIND_HOST}:{PORT} — {exc}")
        sys.exit(1)
    srv.listen(64)
    log(f"Proxy ready: {BIND_HOST}:{PORT} → {LOCAL_HOST}:{PORT} (IP: {ip}) with CORS enabled")
    try:
        while True:
            client, addr = srv.accept()
            threading.Thread(target=handle, args=(client, addr), daemon=True).start()
    except KeyboardInterrupt:
        log("Proxy stopped.")
    finally:
        srv.close()


if __name__ == "__main__":
    main()

