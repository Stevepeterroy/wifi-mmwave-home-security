"""Workspace inventory: compatible enrollment requests plus authenticated links.
Discovery is protocol compatibility, not cryptographic firmware attestation.
"""
from wifi_transport import LINK_TIMEOUT_SECONDS
def inventory(discovery,keys,bridge,home):
 modules={m['id']:m for m in home.get('modules',[])}
 bindings=keys.bindings()
 pending=discovery.list()
 rows=[];seen=set()
 with bridge.lock:
  for module_id,module in modules.items():
   device=bindings.get(module_id)
   channel=bridge.channels.get(module_id)
   paired=keys.has_key(module_id)
   if not device and not channel and not paired:continue
   connected=bool(channel and not channel.closed and 0<=channel.now()-channel.last_seen<=LINK_TIMEOUT_SECONDS)
   candidate=next((p for p in pending if p['deviceId']==device),None)
   status='connected' if connected else 'paused' if module_id in bridge.paused else 'available' if candidate and not candidate['approved'] else 'offline'
   rows.append({'id':device or 'module:'+module_id,'deviceId':device,'name':'ESP32-S3 '+device[-6:] if device else module['name'],'moduleId':module_id,'moduleName':module['name'],'status':status,'paired':paired,'approved':bool(candidate and candidate['approved']),'evidence':'authenticated transport' if connected else 'saved pairing','lastSeenSeconds':round(max(0,channel.now()-channel.last_seen),1) if channel else None})
   if device:seen.add(device)
  for candidate in pending:
   if candidate['deviceId'] in seen:continue
   rows.append({**candidate,'id':candidate['deviceId'],'status':'waiting' if candidate['approved'] else 'available','paired':False,'evidence':'Haven-compatible enrollment request'})
 return rows
