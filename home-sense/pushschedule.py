"""Schedule due trial messages; annotations and service acceptance are not delivery proof."""
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
import time,math
class PushScheduler:
 def __init__(self,store):self.store=store
 def tick(self,home,now=None):
  now=time.time() if now is None else now
  trials=(home or {}).get('trials',[]);active=set()
  for trial in trials:
   try:
    identity=trial['id'];verified=trial['status']=='Cancelled & Verified' and bool(trial.get('proof','').strip())
    end=date.fromisoformat(trial['start'])+timedelta(days=int(trial['days']))
    today=datetime.fromtimestamp(now,ZoneInfo(trial.get('timezone','Asia/Kolkata'))).date()
    interval=float(trial['repeatMinutes'])*60
    if not math.isfinite(interval) or not 60<=interval<=86400:continue
    if verified or today<end-timedelta(days=3):continue
    active.add(identity)
    self.store.queue('trial:'+identity+':'+str(int(now//interval)),{'title':'High priority: '+trial['name'],'body':'Cancel through the provider and record verification in Haven.','tag':'trial-'+identity},now=now,ttl=min(300,int(interval)))
   except (ValueError,TypeError,KeyError,OverflowError):continue
  self.store.cancel_inactive_trials(active)
