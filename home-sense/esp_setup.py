"""Local, authenticated ESP provisioning. Never return credentials or firmware bytes."""
import hashlib,json,os,re,shutil,subprocess,threading,uuid,time
from pathlib import Path
from urllib.parse import urlsplit
from tools.check_wifi_settings import read_settings,validate

FQBN='esp32:esp32:esp32s3:USBMode=hwcdc,CDCOnBoot=default,FlashSize=16M,PSRAM=opi,PartitionScheme=app3M_fat9M_16MB,UploadMode=default,UploadSpeed=115200'

class EspSetup:
 def __init__(self,root,ports,runner=subprocess.run):
  self.root=Path(root);self.ports=ports;self.runner=runner;self.lock=threading.RLock();self.job=None
  self.worker=None
  self.sync_result()
 def sync_result(self):
  if self.worker and self.worker.is_alive():return
  try:
   saved=json.loads((self.root/'data/esp-flash/latest-result.json').read_text())
   if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',saved.get('id','')):return
   if saved.get('state')=='running':
    pid=saved.get('ownerPid')
    if type(pid) is not int or pid<=0:return
    try:os.kill(pid,0)
    except ProcessLookupError:
     folder=self.root/'data/esp-flash'/saved['id']
     upload=folder/'uploading.log'
     output=upload.read_bytes()[-4096:] if upload.exists() else b''
     if b'Hash of data verified.' in output:
      saved.update(state='complete',phase='Firmware installed',backupVerified=True,
       message='Written firmware hash verified; the job owner stopped before recording completion.')
     elif saved.get('phase','').startswith('Backing') and not upload.exists() and (folder/'before-first4MiB.bin').is_file() and (folder/'before-first4MiB.bin').stat().st_size==0x400000 and (folder/'backing.log').is_file() and b'Read 4194304 bytes' in (folder/'backing.log').read_bytes()[-1024:]:
      saved.update(state='failed',phase='Backup completed; upload not started',backupVerified=True,
       message='The ESP backup finished, but no firmware upload ran. The current firmware has not been verified as changed.')
     else:
      saved.update(state='needs_review',message='The job owner stopped. Inspect the USB tool process and private logs before retrying; automatic flashing is blocked.')
     saved['finishedAt']=time.time()
     self.job=saved
     self.persist_result()
   if saved.get('state') in ('running','complete','failed','needs_review'):self.job=saved
  except (OSError,ValueError,TypeError,AttributeError):pass
 def persist_result(self):
  result=self.root/'data/esp-flash/latest-result.json';result.parent.mkdir(parents=True,exist_ok=True)
  temp=result.with_suffix('.pending');temp.write_text(json.dumps(self.job));temp.chmod(0o600);os.replace(temp,result)
 def settings(self):
  return read_settings((self.root/'firmware/rd60_wifi/secrets.h').read_text())
 def tools(self):
  cli=shutil.which('arduino-cli')
  fallback=Path('/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli')
  if not cli and fallback.is_file():cli=str(fallback)
  candidates=list((Path.home()/'Library/Arduino15/packages/esp32/tools/esptool_py').glob('*/esptool'))
  esp=shutil.which('esptool') or next((str(p) for p in sorted(candidates,reverse=True) if os.access(p,os.X_OK)),None)
  return cli,esp
 def status(self):
  with self.lock:
   self.sync_result()
   try:
    s=self.settings();host=urlsplit(s['HAVEN_EXCHANGE_URL']).hostname or ''
    settings={'ssid':s['HAVEN_WIFI_SSID'],'hasPassword':bool(s['HAVEN_WIFI_PASSWORD']),'host':host,'configured':not validate(s)}
   except (ValueError,OSError):settings={'ssid':'','hasPassword':False,'host':'','configured':False}
   cli,esp=self.tools()
   return {**settings,'toolsReady':bool(cli and esp),'ports':self.ports(),'job':self.job_status()}
 def job_status(self):
  if not self.job:return None
  job=dict(self.job);now=time.time()
  job['elapsedSeconds']=max(0,int(job.get('finishedAt',now)-job.get('startedAt',now)))
  job['phaseElapsedSeconds']=max(0,int(job.get('finishedAt',now)-job.get('phaseStartedAt',now)))
  job['progressPercent']=None;job['stalled']=False
  if job['state']=='complete':job['progressPercent']=100
  if job['state']=='running':
   name=job['phase'].split()[0].lower()+'.log'
   path=self.root/'data/esp-flash'/job['id']/name
   try:
    # Read only the tail; never return raw compiler output or credentials.
    with path.open('rb') as log:
     log.seek(0,2);log.seek(max(0,log.tell()-8192));tail=log.read().decode(errors='replace')
    values=re.findall(r'(\d+(?:\.\d+)?)%\s+\d+/\d+\s+bytes',tail)
    if values:job['progressPercent']=min(100,float(values[-1]))
    limit=180 if job['phase'].startswith('Compiling') else 45
    job['stalled']=now-path.stat().st_mtime>limit and job['phaseElapsedSeconds']>limit
   except OSError:pass
  return job
 def save(self,body):
  with self.lock:
   if self.job and self.job['state']=='running':raise ValueError('Wait for the current firmware job to finish')
   if not isinstance(body,dict):raise ValueError('Invalid Wi-Fi settings')
   ssid=body.get('ssid');password=body.get('password');host=body.get('host');open_network=body.get('openNetwork',False)
   if not isinstance(ssid,str) or not ssid or len(ssid.encode())>32:raise ValueError('Wi-Fi name must contain 1–32 bytes')
   if not isinstance(password,str) or type(open_network) is not bool:raise ValueError('Invalid Wi-Fi password')
   if any(ord(c)<32 for c in ssid+password):raise ValueError('Control characters are not allowed')
   s=self.settings();old_host=urlsplit(s['HAVEN_EXCHANGE_URL']).hostname
   if open_network:password=''
   elif not password:
    if ssid!=s['HAVEN_WIFI_SSID'] or not s['HAVEN_WIFI_PASSWORD']:raise ValueError('Enter the password for this network, or explicitly select an open network')
    password=s['HAVEN_WIFI_PASSWORD']
   elif not 8<=len(password.encode())<=63:raise ValueError('Wi-Fi password must contain 8–63 bytes')
   import ipaddress
   try:ip=ipaddress.ip_address(host)
   except (ValueError,TypeError):raise ValueError('Enter the laptop private LAN IPv4 address') from None
   if ip.version!=4 or not ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_multicast:raise ValueError('Enter the laptop private LAN IPv4 address')
   # Regenerate trust only when changing endpoint; unchanged networks do not rotate trust.
   if str(ip)!=old_host:
    from tools.configure_wifi_host import provision
    provision(str(ip),self.root,(ssid,password))
   else:
    s['HAVEN_WIFI_SSID']=ssid;s['HAVEN_WIFI_PASSWORD']=password
    header=self.root/'firmware/rd60_wifi/secrets.h'
    mode=re.search(r'^#define HAVEN_CSI_ONLY [01]$',header.read_text(),re.M)
    backup=self.root/'data/esp-setup'/('settings-'+uuid.uuid4().hex+'.h');backup.parent.mkdir(parents=True,exist_ok=True);backup.parent.chmod(0o700)
    shutil.copy2(header,backup);backup.chmod(0o600)
    source=header.read_text()
    clock_defines=''.join(match.group(0)+'\n' for name in ('HAVEN_TIME_HOST','HAVEN_TIME_KEY') if (match:=re.search(r'^#define '+name+r' "(?:\\.|[^"\\])*"$',source,re.M)))
    content='#pragma once\n// Private settings. Never commit.\n'+''.join('#define '+k+' '+json.dumps(v)+'\n' for k,v in s.items())+(mode[0]+'\n' if mode else '#define HAVEN_CSI_ONLY 1\n')+clock_defines
    temp=backup.parent/(uuid.uuid4().hex+'.pending');temp.write_text(content);temp.chmod(0o600);os.replace(temp,header)
   return {'saved':True,'endpointChanged':str(ip)!=old_host,'requiresFlash':True}
 def start(self,body,occupied=()):
  with self.lock:
   self.sync_result()
   if not isinstance(body,dict) or body.get('confirm') is not True:raise ValueError('Confirm that firmware replacement will stop this ESP’s sensing')
   if self.job and self.job['state'] in ('running','needs_review'):raise ValueError('A firmware job is active or requires inspection before retrying')
   mode=body.get('mode','csi_only')
   if mode not in ('csi_only','csi_radar'):raise ValueError('Choose CSI only or CSI + RD-60')
   if mode=='csi_radar' and body.get('wiringConfirmed') is not True:raise ValueError('Confirm radar wiring and isolated kit UART switches first')
   port=body.get('port')
   if port not in [p['port'] for p in self.ports()]:raise ValueError('Choose a currently connected USB serial port')
   if port in occupied:raise ValueError('Disconnect this port from the sensor reader before flashing')
   cli,esp=self.tools()
   if not cli or not esp:raise ValueError('Install Arduino IDE with the Espressif ESP32 board package first')
   if validate(self.settings()):raise ValueError('Save valid Wi-Fi settings before flashing')
   job={'id':uuid.uuid4().hex,'state':'running','phase':'Preparing private build','mode':mode,'port':port,'ownerPid':os.getpid(),'startedAt':time.time(),'phaseStartedAt':time.time(),'backupVerified':False,'message':'Keep the ESP connected. This can take several minutes.'}
   self.job=job
   self.persist_result()
   self.worker=threading.Thread(target=self.run,args=(job,cli,esp),daemon=True)
   self.worker.start()
   return dict(job)
 def run(self,job,cli,esp):
  folder=self.root/'data/esp-flash'/job['id']
  try:
   folder.mkdir(parents=True,mode=0o700)
   sketch=folder/'rd60_wifi';shutil.copytree(self.root/'firmware/rd60_wifi',sketch)
   private_header=sketch/'secrets.h'
   source=private_header.read_text()
   source=re.sub(r'^#define HAVEN_CSI_ONLY .*$', '', source, flags=re.M)+'\n#define HAVEN_CSI_ONLY '+('0' if job.get('mode')=='csi_radar' else '1')+'\n'
   private_header.write_text(source)
   for p in sketch.iterdir():
    if p.is_file():p.chmod(0o600)
   def execute(args,phase,timeout):
    with self.lock:
     job['phase']=phase;job['phaseStartedAt']=time.time();self.job=job;self.persist_result()
    # Compiler errors can contain private header source; logs never leave private storage.
    with (folder/(phase.split()[0].lower()+'.log')).open('wb') as log:
     self.runner(args,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,check=True)
   build=folder/'build'
   execute([cli,'compile','--fqbn',FQBN,'--build-path',str(build),str(sketch)],'Compiling firmware',600)
   backup=folder/'before-first4MiB.bin'
   execute([esp,'--chip','esp32s3','--port',job['port'],'--baud','115200','read-flash','0','0x400000',str(backup)],'Backing up ESP32-S3 flash',900)
   if backup.stat().st_size!=0x400000:raise ValueError('Backup size verification failed; no firmware was written')
   digest=hashlib.sha256(backup.read_bytes()).hexdigest();(folder/'backup.sha256').write_text(digest+'\n')
   with self.lock:job['backupVerified']=True
   execute([cli,'upload','--fqbn',FQBN,'--port',job['port'],'--input-dir',str(build),str(sketch)],'Uploading and verifying firmware',300)
   with self.lock:job.update(state='complete',finishedAt=time.time(),phase='Firmware installed',message='Find the ESP under Available devices. New devices require enrollment; existing saved pairing is reused only for the same server.')
  except Exception:
   with self.lock:job.update(state='failed',finishedAt=time.time(),message='Setup failed during '+job['phase']+'. Private diagnostic logs and any completed backup are retained locally. Check the USB cable, ESP32-S3 model and installed board package before retrying.')

  finally:
   try:
    result=self.root/'data/esp-flash/latest-result.json'
    result.parent.mkdir(parents=True,exist_ok=True)
    temp=result.with_suffix('.pending');temp.write_text(json.dumps(job));temp.chmod(0o600);os.replace(temp,result)
   except OSError:pass
