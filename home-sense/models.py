"""Workspace scan assets stored by generated IDs, never client paths."""
import json,re,hashlib,os,threading,math
from pathlib import Path
MAX=150*1024*1024
EXT={'.glb','.gltf','.obj','.bin','.png','.jpg','.jpeg','.webp'}
class ModelStore:
 def __init__(self,root):self.root=Path(root);self.root.mkdir(exist_ok=True,parents=True);self.root.chmod(0o700);self.lock=threading.RLock()
 def folder(self,key):
  if not isinstance(key,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',key):raise ValueError('Invalid model ID')
  return self.root/key
 def manifest(self,key):
  file=self.folder(key)/'manifest.json'
  if not file.exists():raise ValueError('Model not found')
  return json.loads(file.read_text())
 def list(self):
  result=[]
  with self.lock:
   for path in self.root.glob('*/manifest.json'):
    m=json.loads(path.read_text())
    if self.ready(m):result.append(m)
  return result
 def ready(self,m):
  folder=self.folder(m['id'])
  return m.get('ready',False) and all((folder/(str(i)+'.blob')).exists() and (folder/(str(i)+'.blob')).stat().st_size==f['size'] for i,f in enumerate(m['files']))
 def prepare(self,m):
  if not isinstance(m,dict):raise ValueError('Invalid model metadata')
  if not isinstance(m.get('name'),str) or not 1<=len(m['name'])<=255 or not isinstance(m.get('created'),str) or len(m['created'])>100:raise ValueError('Invalid model name or creation date')
  folder=self.folder(m.get('id'));files=m.get('files')
  if m.get('id') in self.deleted_ids():raise ValueError('This scan was deleted; import it with a new ID')
  if not isinstance(files,list) or not 1<=len(files)<=200:raise ValueError('Choose model files')
  names=set();total=0
  for f in files:
   if not isinstance(f,dict):raise ValueError('Invalid file metadata')
   name=f.get('name');size=f.get('size');digest=f.get('sha256')
   if not isinstance(name,str) or len(name)>255 or Path(name).name!=name or Path(name).suffix.lower() not in EXT or name in names:raise ValueError('Invalid or duplicate model filename')
   if not isinstance(size,int) or not 0<size<=MAX or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Invalid file size or digest')
   names.add(name);total+=size
  if total>MAX or not any(Path(n).suffix.lower() in {'.glb','.gltf','.obj'} for n in names):raise ValueError('Choose a model below 150 MB')
  scale=m.get('scale')
  if not isinstance(scale,(int,float)) or not .001<=scale<=100:raise ValueError('Invalid model scale')
  up_axis=m.get('upAxis','Y');yaw=m.get('yaw',0)
  if up_axis not in ('Y','Z') or not isinstance(yaw,(int,float)) or not math.isfinite(yaw) or not -360<=yaw<=360:raise ValueError('Invalid scan axis or rotation')
  m={**{k:m[k] for k in ('id','name','created','scale','files')},'upAxis':up_axis,'yaw':yaw}
  with self.lock:
   folder.mkdir(exist_ok=True);folder.chmod(0o700)
   missing=[]
   for i,f in enumerate(files):
    p=folder/(str(i)+'.blob')
    if not p.exists() or p.stat().st_size!=f['size'] or hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:missing.append(i)
   m['missing']=missing;m['ready']=not missing
   path=folder/'manifest.json';temporary=folder/'manifest.tmp';temporary.write_text(json.dumps(m));temporary.chmod(0o600);os.replace(temporary,path)
   return missing
 def upload(self,key,index,stream,length):
  with self.lock:
   m=self.manifest(key)
   if not 0<=index<len(m['files']) or length!=m['files'][index]['size']:raise ValueError('File size does not match metadata')
   folder=self.folder(key);path=folder/(str(index)+'.partial');digest=hashlib.sha256();remaining=length
   try:
    with path.open('wb') as file:
     while remaining:
      chunk=stream.read(min(65536,remaining))
      if not chunk:raise ValueError('Upload ended before the complete file arrived')
      file.write(chunk);digest.update(chunk);remaining-=len(chunk)
    if digest.hexdigest()!=m['files'][index]['sha256']:raise ValueError('File digest mismatch')
    path.chmod(0o600);os.replace(path,folder/(str(index)+'.blob'))
    m['missing']=[i for i in m.get('missing',[]) if i!=index];m['ready']=not m['missing']
    temporary=folder/'manifest.tmp';temporary.write_text(json.dumps(m));temporary.chmod(0o600);os.replace(temporary,folder/'manifest.json')
   finally:
    if path.exists():path.unlink()
 def deleted_ids(self):
  return [p.name for p in (self.root/'.deleted').glob('*') if p.is_dir()]
 def delete(self,key,config):
  with self.lock:
   folder=self.folder(key)
   if config.get('homeModelId')==key:
    raise ValueError('Switch to another active scan before deleting this scan.')
   self.manifest(key)
   archive=self.root/'.deleted';archive.mkdir(exist_ok=True);archive.chmod(0o700)
   os.rename(folder,archive/key)
 def file(self,key,index):
  with self.lock:
   m=self.manifest(key)
   if not self.ready(m) or not 0<=index<len(m['files']):raise ValueError('Model is incomplete or file is missing')
   return self.folder(key)/(str(index)+'.blob'),m['files'][index]['name']
