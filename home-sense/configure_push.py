"""Generate workspace VAPID files; never prints private key material."""
import argparse,base64
from pathlib import Path
from urllib.parse import urlparse
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption

def generate(folder,subject):
 parsed=urlparse(subject)
 if not ((parsed.scheme=='mailto' and '@' in parsed.path) or (parsed.scheme=='https' and parsed.hostname)) or len(subject)>500:raise ValueError('Use your actual mailto contact or HTTPS contact URL')
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);folder.chmod(0o700)
 files=[folder/'vapid-private.pem',folder/'vapid-public.txt',folder/'vapid-subject.txt']
 if any(p.exists() for p in files):raise ValueError('VAPID files already exist; preserve them for current device subscriptions')
 key=ec.generate_private_key(ec.SECP256R1())
 values=[key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()),base64.urlsafe_b64encode(key.public_key().public_bytes(Encoding.X962,PublicFormat.UncompressedPoint)).rstrip(b'='),subject.encode()]
 created=[]
 try:
  for path,value in zip(files,values):
   with path.open('xb') as file:created.append(path);path.chmod(0o600);file.write(value)
 except Exception:
  for path in created:path.unlink()
  raise
 return files
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--subject',required=True);parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent/'data'/'push');args=parser.parse_args()
 generate(args.directory,args.subject);print('VAPID files saved privately. Configure the server environment; no device has been subscribed or message sent.')
