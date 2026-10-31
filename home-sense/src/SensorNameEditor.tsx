import { useEffect, useState } from "react";
import type { Module } from "./domain";
export default function SensorNameEditor({module,onRename}:{module?:Module;onRename:(name:string)=>Promise<void>}) {
 const [name,setName]=useState(module?.name || ""),[busy,setBusy]=useState(false),[error,setError]=useState("");
 useEffect(()=>{setName(module?.name || "");setError("");},[module?.id,module?.name]);
 return <form className="sensor-name-editor" onSubmit={async e=>{
  e.preventDefault();const value=name.trim();
  if(!value || value.length>80){setError("Use a sensor name containing 1–80 characters.");return;}
  setBusy(true);setError("");try{await onRename(value);}catch(e){setError((e as Error).message);}finally{setBusy(false);}
 }}>
  <label>Sensor display name<input value={name} onChange={e=>setName(e.target.value)} maxLength={80} disabled={!module || busy} required autoComplete="off"/></label>
  <button type="submit" disabled={!module || busy || !name.trim() || name.trim()===module.name}>{busy ? "Saving…" : "Save sensor name"}</button>
  <span className="muted small">Renaming keeps the sensor ID, pairing key and placement unchanged.</span>
  {error && <p role="alert">{error}</p>}
 </form>;
}
