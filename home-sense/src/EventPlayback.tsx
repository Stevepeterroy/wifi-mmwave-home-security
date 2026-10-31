import {lazy, memo, Suspense, useEffect, useMemo, useState} from 'react';
import type {Event, Module, Room, Track, WorldPoint} from './domain';
import {transform, withinPlan} from './domain';
import type {ModelAsset} from './assets';
import {useScanFootprint} from './useScanFootprint';
import {homePlanBounds} from './planProjection';
const Scene = lazy(() => import('./Scene'));
const EMPTY_ROOMS:Room[]=[];
const EMPTY_TRACKS:Track[]=[];
export const PLAYBACK_ECHO_SECONDS=12;
export function playbackPoints(samples:NonNullable<Event['samples']>, index:number, placement:Module, seconds=PLAYBACK_ECHO_SECONDS):WorldPoint[] {
 const selected=samples[index];
 if(!selected)return [];
 const end=Date.parse(selected.at);
 return samples.slice(0,index+1).flatMap(sample=>{
  const at=Date.parse(sample.at);
  if(!Number.isFinite(at)||!Number.isFinite(end)||at>end||end-at>seconds*1000)return [];
  return sample.points.filter(p=>[p.x_cm,p.y_cm,p.z_cm,p.velocity_cm_s].every(Number.isFinite)).map(p=>transform(p,placement));
 });
}
export function eventModel(event: Event, models: ModelAsset[]): ModelAsset | undefined {
 const asset=models.find(m=>m.id===event.modelId);
 if (!asset) return undefined;
 const snapshot=event.scanSnapshot;
 // The event snapshot is a server manifest, not hydrated geometry. Never let
 // its metadata-only `files` replace the asset's loadable files/remoteFiles.
 return {...asset,scale:snapshot?.scale ?? asset.scale,upAxis:snapshot?.upAxis ?? asset.upAxis,yaw:snapshot?.yaw ?? asset.yaw};
}
function EventPlayback({event, models}: {event:Event;models:ModelAsset[]}) {
 const [open,setOpen]=useState(false), [index,setIndex]=useState(0), [playing,setPlaying]=useState(false);
 const samples=event.samples || [];
 useEffect(()=>{
  if (!open || !playing || samples.length<2)return;
  const timer=window.setInterval(()=>setIndex(current=>{
   if(current>=samples.length-1){setPlaying(false);return current;}
   return current+1;
  }),700);
  return ()=>window.clearInterval(timer);
 },[open,playing,samples.length]);
 const asset=models.find(m=>m.id===event.modelId);
 const model=useMemo(()=>eventModel(event,models),[asset,event.scanSnapshot?.scale,event.scanSnapshot?.upAxis,event.scanSnapshot?.yaw]);
 const scanState=useScanFootprint(model);
 const bounds=useMemo(()=>scanState?.footprint?homePlanBounds([],scanState.footprint):undefined,[scanState?.footprint]);
 const sample=samples[index];
 const placementKey=JSON.stringify(event.placement);
 const samplesKey=JSON.stringify(samples);
 const modules=useMemo(()=>event.placement?[event.placement]:[],[placementKey]);
 const allPoints=useMemo(()=>event.placement&&bounds?samples.flatMap(s=>s.points.filter(p=>[p.x_cm,p.y_cm,p.z_cm,p.velocity_cm_s].every(Number.isFinite)).map(p=>transform(p,event.placement!))).filter(p=>withinPlan(p,bounds)):[],[samplesKey,placementKey,bounds]);
 const points=useMemo(()=>event.placement&&bounds?playbackPoints(samples,index,event.placement).filter(p=>withinPlan(p,bounds)):[],[samplesKey,index,placementKey,bounds]);
 return <div>
  <button disabled={!samples.length || !event.placement} onClick={()=>{setPlaying(false);setOpen(!open)}}>{open?'Close motion view':'View recorded movement from above'}</button>
  {open && <div>
   <p className="muted small">Top view of partial moving radar reflections, not a person's path. Only echoes within the scanned space are shown, as on the dashboard; point height is ignored. {samples.length} retained previews of {event.sampleCount || samples.length}. Orange echoes remain for up to {PLAYBACK_ECHO_SECONDS} seconds of recorded time. {event.recordingTruncated?'Older previews were dropped at the recording limit.':''}</p>
   {!model ? <p>The original scanned space is unavailable; no substitute map is used.</p> : <>
    {!bounds && <p role="status" className="muted small">{scanState?.error?`Could not determine the scanned-space boundary: ${scanState.error}`:'Finding the scanned-space boundary…'}</p>}
    <div style={{height:300,position:'relative'}}><Suspense fallback={<p>Loading event space…</p>}><Scene rooms={EMPTY_ROOMS} modules={modules} tracks={EMPTY_TRACKS} points={points} pointRadius={0.16} focusPoints={allPoints} model={model} plan planBounds={bounds}/></Suspense></div>
    <p className="muted small">{points.length} radar {points.length===1?'echo':'echoes'} shown inside the scanned space. {event.room.includes('location unverified')?'Sensor placement is unverified; out-of-bounds echoes are hidden, not relocated.':''}</p>
    {samples.length<2 && <p role="status" className="muted small">This event saved only one radar preview, so there is no motion sequence to play. The still frame above is all that was recorded; missing frames cannot be recreated.</p>}
    <div className="playback-controls">
     <button type="button" disabled={samples.length<2} onClick={()=>{if(playing){setPlaying(false)}else{if(index>=samples.length-1)setIndex(0);setPlaying(true)}}} aria-label={playing?'Pause recorded motion':samples.length<2?'Playback unavailable: one saved frame':'Play recorded motion'}>{playing?'Pause':samples.length<2?'No playback':'Play'}</button>
     <label>Recorded motion time<input type="range" min={0} max={Math.max(0,samples.length-1)} value={Math.min(index,Math.max(0,samples.length-1))} onChange={e=>{setPlaying(false);setIndex(Number(e.target.value))}}/></label>
    </div>
    <p>{sample && new Date(sample.at).toLocaleString(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',hour12:true})}</p>
   </>}
  </div>}
 </div>;
}
export default memo(EventPlayback);
