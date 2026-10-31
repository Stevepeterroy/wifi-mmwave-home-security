import {useEffect,useState} from 'react';
import {pairingTarget} from './wifiPairing';
type Device={id:string;deviceId?:string;name:string;moduleId?:string;moduleName?:string;status:string;paired:boolean;approved:boolean;evidence:string;lastSeenSeconds?:number|null};
type Props={request:(path:string,body?:unknown)=>Promise<any>;sensors:{id:string;name:string}[];selectedId?:string;selectedConnected:boolean;onSelect:(id:string)=>void;onAdd:()=>void;save:(id:string)=>Promise<void>};
export default function WifiDevices({request,sensors,selectedId,selectedConnected,onSelect,onAdd,save}:Props){
 const [devices,setDevices]=useState<Device[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false),[loaded,setLoaded]=useState(false);
 const target=pairingTarget(selectedId,selectedConnected,devices);
 async function refresh(){try{setDevices(await request('/api/wifi/inventory'));setLoaded(true);setError('');}catch(e){setDevices([]);setError((e as Error).message);}}
 useEffect(()=>{let active=true;const poll=async()=>{try{const rows=await request('/api/wifi/inventory');if(active){setDevices(rows);setLoaded(true);setError('');}}catch(e){if(active){setDevices([]);setError((e as Error).message);}}};void poll();const timer=setInterval(()=>void poll(),3000);return()=>{active=false;clearInterval(timer);};},[request]);
 return <div aria-label="Haven Wi-Fi ESP devices">
  <h3>Haven ESPs on Wi-Fi</h3>
  <button onClick={onAdd}>Add a sensor for another ESP</button>
  <button disabled={busy} onClick={()=>void refresh()}>Find available ESPs</button>
  <p className="muted small">Only devices speaking Haven’s firmware protocol and reaching this server appear. Discovery is not a router-wide scan or proof of firmware authenticity. Paired devices are retained below when offline.</p>
  <label className="wifi-pairing-target">Sensor to connect or view
   <select aria-label="Sensor to connect or view" value={selectedId || ''} onChange={e=>onSelect(e.target.value)}>
    <option value="" disabled>Choose a sensor</option>
    {sensors.map(s=><option key={s.id} value={s.id}>{s.name}{devices.some(d=>d.moduleId===s.id&&d.paired)?' · paired':''}</option>)}
   </select>
  </label>
  <p className="muted small" role="status">{target.reason}</p>
  {error&&<p role="alert">{error}</p>}
  {loaded&&!devices.length&&!error&&<p>No Haven ESPs detected yet. Power an ESP flashed with Haven firmware, configured for this Wi-Fi and this server’s HTTPS address.</p>}
  {devices.map(d=><div className="saved-recording" key={d.id}>
   <strong>{d.name}</strong><p>{d.deviceId?`Device ${d.deviceId} · `:''}{d.moduleName?`Sensor: ${d.moduleName} · `:''}{d.status==='connected'?'Connected to Haven':d.status==='paused'?'Connection paused':d.status==='available'?'Available to connect':d.status==='waiting'?'Approved — waiting for connection':'Offline / waiting for ESP'}</p>
   <p className="muted small">{d.evidence}{d.lastSeenSeconds!=null?` · last transport contact ${d.lastSeenSeconds}s ago`:''}</p>
   {d.moduleId&&(d.moduleId===selectedId?<span className="muted small">Viewing this sensor</span>:<button disabled={busy} onClick={()=>onSelect(d.moduleId!)}>View sensor</button>)}
   {d.moduleId&&d.paired&&d.status!=='connected'&&d.status!=='available'&&<button disabled={busy} onClick={async()=>{setBusy(true);try{await request('/api/wifi/reset',{moduleId:d.moduleId});await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>Allow reconnection</button>}
   {d.moduleId&&d.deviceId&&d.paired&&<button disabled={busy} onClick={async()=>{if(!window.confirm(`Forget ESP ${d.deviceId} from ${d.moduleName}? This revokes its pairing key and disconnects it. The sensor and saved recordings remain.`))return;setBusy(true);try{await request('/api/wifi/forget',{moduleId:d.moduleId,deviceId:d.deviceId});await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>Forget ESP</button>}
   {d.status==='available'&&!d.paired&&<button disabled={busy||!target.ready||!d.deviceId} onClick={async()=>{if(!selectedId||!d.deviceId)return;setBusy(true);try{await save(selectedId);await request('/api/wifi/approve',{deviceId:d.deviceId,moduleId:selectedId});await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>Connect to {sensors.find(s=>s.id===selectedId)?.name || 'selected sensor'}</button>}
  </div>)}
 </div>;
}
