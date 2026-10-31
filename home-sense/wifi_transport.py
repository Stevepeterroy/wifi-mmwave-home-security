"""Bounded, authenticated HTTP polling bridge for the existing ESP diagnostics.

Device credentials authorize only their module's stream, never workspace access.
Raw bytes are base64 so retries and serial line boundaries are preserved.
"""
import base64,hashlib,hmac,re,secrets,threading,time
from collections import deque
from database import connection

ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
LINK_TIMEOUT_SECONDS = 8  # Allow short Wi-Fi/TLS stalls without dropping an active ESP.

class DeviceKeys:
    def __init__(self, db): self.db = db
    def prepare(self):
        with connection(self.db()) as db:
            db.execute('CREATE TABLE IF NOT EXISTS device_keys (module TEXT PRIMARY KEY, digest TEXT NOT NULL)')
    def has_key(self,module):
        self.prepare()
        with connection(self.db()) as db:return db.execute('SELECT 1 FROM device_keys WHERE module=?',(module,)).fetchone() is not None
    def bind(self,module,device):
        self.prepare()
        if not isinstance(device,str) or not re.fullmatch(r'[A-Fa-f0-9]{12}',device):raise ValueError('Invalid ESP identity')
        with connection(self.db()) as db:
            db.execute('CREATE TABLE IF NOT EXISTS device_bindings (module TEXT PRIMARY KEY, device TEXT UNIQUE NOT NULL)')
            db.execute('DELETE FROM device_bindings WHERE device=?',(device,))
            db.execute('INSERT OR REPLACE INTO device_bindings VALUES (?,?)',(module,device))
    def bindings(self):
        self.prepare()
        with connection(self.db()) as db:
            db.execute('CREATE TABLE IF NOT EXISTS device_bindings (module TEXT PRIMARY KEY, device TEXT UNIQUE NOT NULL)')
            return dict(db.execute('SELECT module,device FROM device_bindings'))
    def issue(self,module):
        if not isinstance(module,str) or not ID.fullmatch(module):raise ValueError('Invalid module identity')
        self.prepare();token=secrets.token_urlsafe(32)
        with connection(self.db()) as db:
            db.execute('INSERT OR REPLACE INTO device_keys VALUES (?,?)',(module,hashlib.sha256(token.encode()).hexdigest()))
        return token
    def verify(self,module,token):
        if not isinstance(token,str) or len(token)>100:return False
        self.prepare()
        with connection(self.db()) as db:row=db.execute('SELECT digest FROM device_keys WHERE module=?',(module,)).fetchone()
        return bool(row and hmac.compare_digest(row[0],hashlib.sha256(token.encode()).hexdigest()))
    def revoke(self,module):
        self.prepare()
        with connection(self.db()) as db:db.execute('DELETE FROM device_keys WHERE module=?',(module,))
    def forget(self,module,device):
        """Remove one explicitly identified pairing, not the sensor or its history."""
        self.prepare()
        with connection(self.db()) as db:
            db.execute('CREATE TABLE IF NOT EXISTS device_bindings (module TEXT PRIMARY KEY, device TEXT UNIQUE NOT NULL)')
            row=db.execute('SELECT device FROM device_bindings WHERE module=?',(module,)).fetchone()
            if not row or row[0]!=device:raise ValueError('ESP pairing changed; refresh the device list')
            db.execute('DELETE FROM device_keys WHERE module=?',(module,))
            db.execute('DELETE FROM device_bindings WHERE module=? AND device=?',(module,device))

class PollSerial:
    """Serial-compatible stream scoped to a single boot and verified reader."""
    def __init__(self,boot,now=time.monotonic):
        self.boot=boot;self.now=now;self.last_seen=now();self.lock=threading.Condition()
        self.buffer=bytearray();self.commands=deque();self.sequence=-1;self.cached=None;self.fingerprint=None;self.closed=False
    def exchange(self,body):
        if not isinstance(body,dict):raise ValueError('Expected a device packet')
        if body.get('boot')!=self.boot:raise ValueError('ESP restarted; reconnect the module before scanning')
        seq=body.get('sequence');age=body.get('age_ms')
        if type(seq) is not int or not 0<=seq<2**53 or type(age) is not int or not 0<=age<=1000:raise ValueError('Invalid sequence or stale data')
        encoded=body.get('data')
        if not isinstance(encoded,str) or len(encoded)>12000:raise ValueError('Device packet too large')
        try:data=base64.b64decode(encoded,validate=True)
        except (ValueError,TypeError) as exc:raise ValueError('Invalid byte encoding') from exc
        if len(data)>8192:raise ValueError('Device packet too large')
        with self.lock:
            if self.closed:raise ValueError('Reader closed; reconnect the module')
            if self.now()-self.last_seen>LINK_TIMEOUT_SECONDS:
                self.closed=True;self.lock.notify_all();raise ValueError('Wi-Fi connection expired; reconnect the module')
            if seq==self.sequence:
                if self.fingerprint!=hashlib.sha256(data).digest():raise ValueError('Changed retry payload')
                self.last_seen=self.now();return self.cached
            if seq!=self.sequence+1:raise ValueError('Out-of-order device packet')
            if len(self.buffer)+len(data)>65536:
                self.closed=True;self.lock.notify_all();raise ValueError('Wi-Fi receive overflow; reconnect the module')
            self.last_seen=self.now();self.buffer.extend(data)
            commands=list(self.commands);self.commands.clear()
            self.sequence=seq;self.fingerprint=hashlib.sha256(data).digest();self.cached={'accepted':seq,'commands':commands}
            self.lock.notify_all();return self.cached
    @property
    def in_waiting(self):
        with self.lock:return len(self.buffer)
    def read(self,n):
        with self.lock:
            if not self.buffer and not self.closed:self.lock.wait(.05)
            if self.closed or self.now()-self.last_seen>LINK_TIMEOUT_SECONDS:raise OSError('ESP Wi-Fi connection lost')
            value=bytes(self.buffer[:n]);del self.buffer[:n];return value
    def write(self,data):
        value=data.decode('ascii').strip()
        if not value or len(value)>128 or '\n' in value or '\r' in value:raise ValueError('Invalid diagnostic command')
        with self.lock:
            if self.closed or self.now()-self.last_seen>LINK_TIMEOUT_SECONDS:raise OSError('ESP Wi-Fi connection lost')
            if len(self.commands)>=32:raise OSError('ESP command queue full')
            self.commands.append(value)
        return len(data)
    def flush(self):pass
    def close(self):
        with self.lock:self.closed=True;self.lock.notify_all()

class WifiBridge:
    def __init__(self):self.lock=threading.RLock();self.channels={};self.retired_boots={};self.paused=set()
    def exchange(self,module,body,registry):
        boot=body.get('boot') if isinstance(body,dict) else None
        mode=body.get('sensor_mode','radar') if isinstance(body,dict) else 'radar'
        if mode not in ('radar','csi_only'):raise ValueError('Invalid sensor mode')
        if mode=='csi_only' and body.get('data')!='':raise ValueError('CSI-only delivery cannot contain radar diagnostics')
        if not isinstance(boot,str) or not re.fullmatch(r'[a-f0-9]{16,64}',boot):raise ValueError('Invalid ESP boot identity')
        with self.lock:
            if module in self.paused:raise ValueError('Wi-Fi delivery paused; reset the Wi-Fi connection in Haven to reconnect')
            if boot in self.retired_boots.get(module,()):raise ValueError('Retired ESP session; restart with a fresh boot identity')
            channel=self.channels.get(module)
            if channel is not None and getattr(channel,'sensor_mode','radar')!=mode and not (
                boot!=channel.boot and (channel.closed or channel.now()-channel.last_seen>LINK_TIMEOUT_SECONDS)
            ):
                raise ValueError('Disconnect before changing sensor mode')
            if channel is not None and boot!=channel.boot and (channel.closed or channel.now()-channel.last_seen>LINK_TIMEOUT_SECONDS):
                # A fresh boot can recover an expired connection, never a live one.
                replacement=PollSerial(boot);replacement.sensor_mode=mode;response=replacement.exchange(body)
                channel.close()
                retire=getattr(registry,'retire_wifi',None)
                if retire:retire(module)
                if mode=='radar':registry.connect_wifi(module,replacement)
                self.retired_boots.setdefault(module,deque(maxlen=64)).append(channel.boot)
                self.channels[module]=replacement
                return response
            if channel is None:
                # Validate the first envelope before starting any reader.
                channel=PollSerial(boot);channel.sensor_mode=mode;response=channel.exchange(body)
                if mode=='radar':registry.connect_wifi(module,channel)
                self.channels[module]=channel
                return response
            return channel.exchange(body)
    def disconnect(self,module,pause=False):
        with self.lock:
            if pause:self.paused.add(module)
            else:self.paused.discard(module)
            channel=self.channels.pop(module,None)
            if channel:channel.close()
