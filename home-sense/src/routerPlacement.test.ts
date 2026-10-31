import {describe,it,expect} from "vitest";
import {initialConfig} from "./domain";
import {placeRouter,visibleRouter,storedRouter,updateRouter} from "./routerPlacement";
const scan={id:"scan-a",scale:1,upAxis:"Y" as const,yaw:0};
const footprint={width:4,depth:5,height:2};
describe("reviewed router placement",()=>{
 it("is optional in existing homes and never invents a location",()=>{
  expect(visibleRouter(initialConfig,scan,footprint)).toBeUndefined();
 });
 it("round trips placement without moving sensors or requiring a room boundary",()=>{
  const cfg={...initialConfig,rooms:[]};
  const placed=placeRouter(cfg,{x:1.25,z:2.5},scan,footprint);
  expect(placed.modules).toBe(cfg.modules);expect(placed.rooms).toBe(cfg.rooms);
  expect(visibleRouter(JSON.parse(JSON.stringify(placed)),scan,footprint)).toMatchObject({x:1.25,z:2.5,planModelId:"scan-a",height:1.2});
 });
 it("rejects invalid, unprocessed and out-of-bounds taps",()=>{
  expect(()=>placeRouter(initialConfig,{x:1,z:1},scan)).toThrow(/processing/);
  for(const p of [{x:NaN,z:1},{x:Infinity,z:1},{x:-1,z:1},{x:4,z:1},{x:1,z:5}])expect(()=>placeRouter(initialConfig,p,scan,footprint)).toThrow();
 });
 it("keeps router positions separate for each scan and hides outdated alignment",()=>{
  const placed=placeRouter(initialConfig,{x:1,z:1},scan,footprint);
  for(const next of [{...scan,id:"other"},{...scan,scale:2},{...scan,yaw:90},{...scan,upAxis:"Z" as const}])expect(visibleRouter(placed,next,footprint)).toBeUndefined();
  expect(visibleRouter(placed,scan,{...footprint,width:3})).toBeUndefined();
  const two=placeRouter(placed,{x:2,z:3},{...scan,id:"other"},footprint);
  expect(two.routers).toHaveLength(2);expect(visibleRouter(two,scan,footprint)?.x).toBe(1);
 });
 it("replaces the current scan router and preserves reviewed details",()=>{
  let placed=placeRouter(initialConfig,{x:1,z:1},scan,footprint);
  placed=updateRouter(placed,storedRouter(placed,scan)!.id,{height:1.8,name:"Hall router"});
  placed=placeRouter(placed,{x:3.9999,z:2},scan,footprint);
  expect(placed.routers).toHaveLength(1);expect(visibleRouter(placed,scan,footprint)).toMatchObject({name:"Hall router",height:1.8});
  expect(visibleRouter(placed,scan,footprint)!.x).toBeLessThan(4);
  expect(visibleRouter(placed,scan,{...footprint,width:2})).toBeUndefined();
 });
 it("supports schematic placement without leaking into a GLB and validates metadata",()=>{
  const placed=placeRouter(initialConfig,{x:1,z:1});
  expect(visibleRouter(placed)?.x).toBe(1);expect(visibleRouter(placed,scan,footprint)).toBeUndefined();
  for(const height of [NaN,Infinity,-1,21])expect(()=>updateRouter(placed,placed.routers![0].id,{height})).toThrow();
  expect(()=>updateRouter(placed,placed.routers![0].id,{name:" "})).toThrow();
 });
});
