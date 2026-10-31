import unittest,tempfile,base64
from pathlib import Path
from webpush import PushStore,validate_subscription,WebPush
from unittest.mock import patch

def subscription(endpoint='https://fcm.googleapis.com/fcm/send/test'):
 return {'endpoint':endpoint,'keys':{'auth':base64.urlsafe_b64encode(b'a'*16).decode().rstrip('='),'p256dh':base64.urlsafe_b64encode(b'\x04'+b'a'*64).decode().rstrip('=')}}
class PushTests(unittest.TestCase):
 def test_provider_and_key_validation(self):
  self.assertEqual(validate_subscription(subscription())['endpoint'],subscription()['endpoint'])
  for endpoint in ['http://fcm.googleapis.com/test','https://127.0.0.1/test','https://fcm.googleapis.com.evil.test/x','https://user@fcm.googleapis.com/test']:
   with self.assertRaises(ValueError):validate_subscription(subscription(endpoint))
  with self.assertRaises(ValueError):validate_subscription({'endpoint':subscription()['endpoint'],'keys':{'auth':'a','p256dh':'b'}})
 def test_durable_deduplication_and_service_acceptance(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'push.sqlite';store=PushStore(path);store.subscribe(subscription());store.subscribe(subscription());store.queue('motion-1',{'title':'Review motion'});store.queue('motion-1',{'title':'Review motion'})
   store=PushStore(path);self.assertEqual(store.summary()['devices'],1);calls=[];store.deliver(lambda s,p:calls.append(p) or 201,100)
   self.assertEqual(len(calls),1);self.assertEqual(store.summary()['states'],{'accepted_by_push_service':1});store.deliver(lambda s,p:201,200);self.assertEqual(len(calls),1)
 def test_bounded_retry_and_expired_subscription(self):
  with tempfile.TemporaryDirectory() as folder:
   store=PushStore(Path(folder)/'push.sqlite');store.subscribe(subscription());store.queue('trial-1',{'title':'Cancel trial'})
   for now in [0,100,300,600,1000]:store.deliver(lambda s,p:503,now)
   self.assertEqual(store.summary()['states'],{'failed':1});store.queue('trial-2',{'title':'Cancel trial'});store.deliver(lambda s,p:410,2000);self.assertEqual(store.summary()['devices'],0)
 def test_expired_message_is_not_sent(self):
  with tempfile.TemporaryDirectory() as folder:
   store=PushStore(Path(folder)/'push.sqlite');store.subscribe(subscription());store.queue('old-motion',{'title':'Review motion'},now=0,ttl=60)
   calls=[];store.deliver(lambda s,p:calls.append(p) or 201,61)
   self.assertEqual(calls,[]);self.assertEqual(store.summary()['states'],{'expired':1})
 def test_unconfigured_delivery_is_refused(self):
  with patch.dict('os.environ',{},clear=True):
   self.assertFalse(WebPush().configured)
   with self.assertRaises(ValueError):WebPush().send(subscription(),{})
if __name__=='__main__':unittest.main()
