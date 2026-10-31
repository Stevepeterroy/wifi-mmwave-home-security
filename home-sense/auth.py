"""Local enrollment and authenticated deployment primitives; no preset credentials."""
from database import connection
import hashlib,hmac,secrets,sqlite3,time,json,threading
class Auth:
 def __init__(self,db):
  self.db=db;self.lock=threading.RLock();self.sessions={};self.failures=[]
  with connection(db) as c:c.execute('CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY,salt TEXT NOT NULL,digest TEXT NOT NULL)')
 @property
 def enrolled(self):
  with connection(self.db) as c:return c.execute('SELECT 1 FROM account WHERE id=1').fetchone() is not None
 def digest(self,password,salt):return hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
 def setup(self,password):
  if not isinstance(password,str) or not 12<=len(password)<=128:raise ValueError('Choose a password between 12 and 128 characters')
  with self.lock:
   if self.enrolled:raise ValueError('Sign-in is already configured')
   salt=secrets.token_hex(16);digest=self.digest(password,salt)
   with connection(self.db) as c:c.execute('INSERT INTO account VALUES (1,?,?)',(salt,digest))
   return self.session()
 def session(self):
  token=secrets.token_urlsafe(32);self.sessions[token]=time.time()+43200;return token
 def login(self,password):
  if not isinstance(password,str) or len(password)>128:raise ValueError('Incorrect password')
  with self.lock:
   self.failures=[t for t in self.failures if time.time()-t<900]
   if len(self.failures)>=5:raise ValueError('Too many attempts. Wait 15 minutes before retrying')
   with connection(self.db) as c:row=c.execute('SELECT salt,digest FROM account WHERE id=1').fetchone()
   if not row or not hmac.compare_digest(self.digest(password,row[0]),row[1]):
    self.failures.append(time.time());raise ValueError('Incorrect password')
   self.failures=[];return self.session()
 def authenticated(self,cookie):
  from http.cookies import SimpleCookie
  try:parsed=SimpleCookie(cookie or '');token=parsed['haven_session'].value
  except (KeyError,TypeError):return False
  with self.lock:
   if self.sessions.get(token,0)<=time.time():self.sessions.pop(token,None);return False
   return True
 def logout(self,cookie):
  from http.cookies import SimpleCookie
  try:token=SimpleCookie(cookie or '')['haven_session'].value
  except (KeyError,TypeError):return
  with self.lock:self.sessions.pop(token,None)
