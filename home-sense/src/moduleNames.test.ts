import {describe,it,expect} from "vitest";
import {initialConfig} from "./domain";
import {renameSensor} from "./moduleNames";
describe("sensor display names",()=>{
 it("changes only the name, not pairing identity, placement or other sensors",()=>{
  const module=initialConfig.modules[0];
  const cfg={...initialConfig,activeModuleId:module.id,modules:[module,{...module,id:"second"}]};
  const renamed=renameSensor(cfg,module.id,"  Bedroom ESP  ");
  expect(renamed.modules[0]).toEqual({...module,name:"Bedroom ESP"});
  expect(renamed.modules[1]).toBe(cfg.modules[1]);expect(renamed.activeModuleId).toBe(module.id);
  expect(renamed.rooms).toBe(cfg.rooms);
 });
 it("rejects blank names, control characters and missing identities",()=>{
  for(const value of [" ","a".repeat(81),"ESP\nname"])expect(()=>renameSensor(initialConfig,initialConfig.modules[0].id,value)).toThrow();
  expect(()=>renameSensor(initialConfig,"unknown","New name")).toThrow();
 });
});
