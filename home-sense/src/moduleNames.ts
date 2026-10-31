import type {Config} from "./domain";
export function renameSensor(config:Config,id:string,name:string):Config {
 const clean=name.trim();
 if(!clean || clean.length>80 || /[\u0000-\u001f]/.test(clean))throw Error("Use a sensor name containing 1–80 printable characters.");
 if(!config.modules.some(m=>m.id===id))throw Error("Choose a registered sensor.");
 return {...config,modules:config.modules.map(m=>m.id===id ? {...m,name:clean} : m)};
}
