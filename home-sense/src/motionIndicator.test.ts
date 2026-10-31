import {describe,it,expect} from 'vitest';
import {motionIndicator} from './motionIndicator';
describe('dashboard motion indicator',()=>{
 it('does not turn an offline or uncalibrated sensor into a motion claim',()=>{
  expect(motionIndicator(false,{radar_motion:true}).value).toBe('Unavailable');
  expect(motionIndicator(true,undefined,true).value).toBe('Setup needed');
 });
 it('distinguishes corroborated and single-source evidence',()=>{
  expect(motionIndicator(true,{status:'corroborated_motion',csi_motion:true,radar_motion:true}).value).toBe('Motion signal');
  expect(motionIndicator(true,{status:'partial_evidence',radar_motion:true}).value).toBe('Motion signal');
  expect(motionIndicator(true,{status:'partial_evidence',csi_motion:true}).value).toBe('Motion signal');
  expect(motionIndicator(true,{status:'sources_disagree',csi_motion:true,radar_motion:false}).value).toBe('Mixed signals');
 });
 it('does not equate no motion with an empty room',()=>{
  const reading=motionIndicator(true,{csi_motion:false,radar_motion:false});
  expect(reading.value).toBe('No motion signal');
  expect(reading.detail).toContain('does not mean the room is empty');
 });
});
