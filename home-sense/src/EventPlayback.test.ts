import {describe,expect,it} from 'vitest';
import {eventModel,playbackPoints} from './EventPlayback';
import {initialConfig} from './domain';
import type {Event} from './domain';
import type {ModelAsset} from './assets';

describe('recorded movement model',()=>{
 it('keeps loadable geometry when the event snapshot includes metadata-only files',()=>{
  const asset:ModelAsset={id:'scan-1',name:'room.glb',created:'2026-10-22',files:[],remoteFiles:[{name:'room.glb',size:12,sha256:'abc'}],scale:1,upAxis:'Y',yaw:0};
  const event:Event={id:'event-1',at:'2026-10-22T00:00:00Z',room:'Room',kind:'Motion',source:'live',acknowledged:false,modelId:'scan-1',scanSnapshot:{scale:2,upAxis:'Z',yaw:45,files:[{name:'room.glb',size:12,sha256:'abc'}]}};
  const model=eventModel(event,[asset]);
  expect(model?.files).toEqual([]);
  expect(model?.remoteFiles).toEqual(asset.remoteFiles);
  expect(model?.scale).toBe(2);
  expect(model?.upAxis).toBe('Z');
  expect(model?.yaw).toBe(45);
 });
 it('keeps recent echoes for twelve recorded seconds without inventing new points',()=>{
  const placement={...initialConfig.modules[0],x:0,z:0,yaw:0};
  const point={point_index:0,x_cm:100,y_cm:100,z_cm:0,velocity_cm_s:70};
  const samples=[0,8,16].map((seconds,i)=>({at:new Date(100000+seconds*1000).toISOString(),sequence:i,points:[point]}));
  expect(playbackPoints(samples,1,placement)).toHaveLength(2);
  expect(playbackPoints(samples,2,placement)).toHaveLength(2);
 });
});
