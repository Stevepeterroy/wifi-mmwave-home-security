import http.client,socket,ssl,tempfile,subprocess,threading,unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from tls_server import DeviceTLSServer
class TlsConcurrencyTests(unittest.TestCase):
 def test_silent_handshake_does_not_block_healthy_clients(self):
  with tempfile.TemporaryDirectory() as tmp:
   cert=Path(tmp)/'cert.pem';key=Path(tmp)/'key.pem'
   subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
   class Handler(BaseHTTPRequestHandler):
    def do_GET(self):self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'ok')
    def log_message(self,*args):pass
   server=DeviceTLSServer(('127.0.0.1',0),Handler,context,handshake_timeout=3)
   threading.Thread(target=server.serve_forever,daemon=True).start()
   silent=socket.create_connection(server.server_address)
   try:
    # This client must finish before the silent peer's three-second deadline.
    client=http.client.HTTPSConnection('localhost',server.server_port,context=ssl.create_default_context(cafile=str(cert)),timeout=1)
    client.request('GET','/');response=client.getresponse();self.assertEqual(response.status,200);self.assertEqual(response.read(),b'ok');client.close()
   finally:silent.close();server.shutdown();server.server_close()
