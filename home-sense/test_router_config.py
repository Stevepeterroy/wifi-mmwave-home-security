import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from database import connection

class RouterConfigTests(unittest.TestCase):
 def test_router_metadata_round_trips_without_requiring_router_on_old_configs(self):
  import server
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'home.sqlite3'
   with connection(db) as c:c.execute('CREATE TABLE config (id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
   home={'rooms':[],'modules':[],'events':[]}
   with patch.object(server,'DB',db):
    server.save_config(home);self.assertNotIn('routers',server.get_config())
    router={'id':'router:scan-a','name':'Router','x':1.2,'z':2.3,'height':1.5,'planModelId':'scan-a','scanAlignment':{'scale':1,'upAxis':'Y','yaw':0},'scanExtent':{'width':4,'depth':5}}
    server.save_config({**home,'routers':[router]});self.assertEqual(server.get_config()['routers'],[router])
    server.save_config({**server.get_config(),'routers':[]});self.assertEqual(server.get_config()['routers'],[])
