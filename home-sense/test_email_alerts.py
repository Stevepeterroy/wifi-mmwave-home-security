import unittest,tempfile
from pathlib import Path
from unittest.mock import patch,MagicMock
from email_alerts import EmailAlerts
class EmailTests(unittest.TestCase):
 def test_five_minute_limit_survives_restart_and_tests_do_not_consume_it(self):
  with tempfile.TemporaryDirectory() as d, patch('email_alerts.threading.Thread.start'):
   a=EmailAlerts(Path(d)/'settings.json')
   a.save(dict(recipient='r@example.com',sender='s@example.com',host='smtp.example.com',port=587,security='starttls',username='user',password='secret',enabled=True))
   with patch('email_alerts.time.time',return_value=1000):
    self.assertTrue(a.enqueue(test=True));self.assertTrue(a.enqueue({'source':'live'}))
   with patch('email_alerts.time.time',return_value=1299):
    self.assertFalse(a.enqueue({'source':'live'}))
    b=EmailAlerts(a.path);self.assertFalse(b.enqueue({'source':'live'}))
   with patch('email_alerts.time.time',return_value=1300):self.assertTrue(b.enqueue({'source':'live'}))
 def test_full_queue_does_not_consume_cooldown(self):
  with tempfile.TemporaryDirectory() as d, patch('email_alerts.threading.Thread.start'):
   a=EmailAlerts(Path(d)/'settings.json')
   a.save(dict(recipient='r@example.com',sender='s@example.com',host='smtp.example.com',port=587,security='starttls',username='user',password='secret',enabled=True))
   for _ in range(32):a.jobs.put_nowait(({},None,True))
   self.assertFalse(a.enqueue({'source':'live'}));self.assertFalse(a.cooldown_path.exists())
 def test_missing_password_blocks_delivery_before_network_access(self):
  with tempfile.TemporaryDirectory() as d:
   a=EmailAlerts(Path(d)/'settings.json')
   c=dict(recipient='r@example.com',sender='s@example.com',host='smtp.example.com',port=587,security='starttls',username='user',password='',enabled=True)
   a.save(c)
   self.assertIn('App Password is missing',a.status()['lastDelivery'])
   self.assertFalse(a.enqueue({'source':'live'}));self.assertFalse(a.enqueue(test=True))
   with patch('email_alerts.smtplib.SMTP') as smtp:
    with self.assertRaises(ValueError):a.send(c,None,True)
    smtp.assert_not_called()
 def test_secret_and_permissions(self):
  with tempfile.TemporaryDirectory() as d:
   a=EmailAlerts(Path(d)/'settings.json');c=dict(recipient='r@example.com',sender='s@example.com',host='smtp.example.com',port=587,security='starttls',username='user',password='secret',enabled=True)
   a.save(c);self.assertNotIn('password',a.status());self.assertEqual(a.path.stat().st_mode&0o777,0o600)
   a.save({**c,'password':''});self.assertEqual(a.config()['password'],'secret')
   with self.assertRaises(ValueError):a.save({**c,'recipient':'r@example.com\nBcc:bad@example.com'})
 def test_tls_and_message(self):
  with tempfile.TemporaryDirectory() as d:
   a=EmailAlerts(Path(d)/'settings.json');c=dict(recipient='r@example.com',sender='s@example.com',host='smtp.example.com',port=587,security='starttls',username='user',password='secret',enabled=True)
   with patch('email_alerts.smtplib.SMTP') as smtp:
    a.send(c,{'room':'Hall','at':'now'},False);client=smtp.return_value.__enter__.return_value
    client.starttls.assert_called_once();client.login.assert_called_once_with('user','secret');m=client.send_message.call_args.args[0];self.assertEqual(m['To'],'r@example.com')
   self.assertFalse(a.enqueue({'source':'recorded'}))
