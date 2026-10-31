import {describe,it,expect} from 'vitest';
import {pairingTarget} from './wifiPairing';
describe('Wi-Fi pairing target',()=>{
 it('blocks connected and previously paired sensors',()=>{
  expect(pairingTarget('a',true,[]).ready).toBe(false);
  expect(pairingTarget('a',false,[{moduleId:'a',paired:true,status:'offline'}]).ready).toBe(false);
 });
 it('allows a separate unused sensor',()=>{
  const devices=[{moduleId:'a',paired:true,status:'connected'},{paired:false,status:'available'}];
  expect(pairingTarget('b',false,devices).ready).toBe(true);
 });
});
