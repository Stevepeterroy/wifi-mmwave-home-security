"""Short-lived ESP enrollment requests; credentials delivered only to requester."""
import re,secrets,threading,time

class DeviceDiscovery:
    def __init__(self, now=time.monotonic):
        self.now=now;self.lock=threading.RLock();self.pending={}
    def prune(self):
        self.pending={k:v for k,v in self.pending.items() if self.now()-v['seen']<60}
    def announce(self, body):
        if not isinstance(body,dict):raise ValueError('Invalid discovery request')
        device=body.get('deviceId');secret=body.get('requestSecret')
        if not isinstance(device,str) or not re.fullmatch(r'[A-Fa-f0-9]{12}',device):raise ValueError('Invalid ESP identity')
        if not isinstance(secret,str) or not re.fullmatch(r'[a-f0-9]{32,64}',secret):raise ValueError('Invalid enrollment request')
        with self.lock:
            self.prune();old=self.pending.get(device)
            if old and not secrets.compare_digest(old['secret'],secret):raise ValueError('An enrollment request is already active for this ESP')
            if not old:
                if len(self.pending)>=32:raise ValueError('Discovery queue full')
                old={'deviceId':device,'secret':secret,'seen':self.now(),'approval':None};self.pending[device]=old
            old['seen']=self.now()
            return old['approval'] or {'pending':True}
    def list(self):
        with self.lock:
            self.prune()
            return [{'deviceId':v['deviceId'],'name':'ESP32-S3 '+v['deviceId'][-6:],'approved':bool(v['approval'])} for v in self.pending.values()]
    def forget(self,device):
        with self.lock:self.pending.pop(device,None)
    def approve(self, device, module, keys):
        with self.lock:
            self.prune();candidate=self.pending.get(device)
            if not candidate:raise ValueError('ESP is no longer available')
            if candidate['approval']:raise ValueError('ESP is already approved')
            if any(v['approval'] and v['approval']['moduleId']==module for v in self.pending.values()):raise ValueError('Another ESP is already assigned to this sensor')
            if hasattr(keys,'bind'):keys.bind(module,device)
            candidate['approval']={'moduleId':module,'deviceToken':keys.issue(module)}
