"""Threaded TLS handshakes: an idle peer must not block the accept loop."""
import ssl
from http.server import ThreadingHTTPServer
class DeviceTLSServer(ThreadingHTTPServer):
 daemon_threads=True
 def __init__(self,address,handler,context,handshake_timeout=5):
  self.handshake_timeout=handshake_timeout
  super().__init__(address,handler)
  self.socket=context.wrap_socket(self.socket,server_side=True,do_handshake_on_connect=False)
 def process_request_thread(self,request,address):
  try:
   request.settimeout(self.handshake_timeout)
   request.do_handshake()
  except (OSError,ssl.SSLError):
   self.shutdown_request(request)
   return
  super().process_request_thread(request,address)
