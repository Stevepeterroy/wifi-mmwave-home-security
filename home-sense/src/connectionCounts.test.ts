import {describe,it,expect} from 'vitest';
import {connectionCounts} from './connectionCounts';
describe('connection counts', () => {
 it('counts CSI-only ESPs separately from verified radars', () => {
  expect(connectionCounts(['a','b','c'], {a:{csi:{connected:true}}, b:{connected:true,radar_verified:true}, c:{connected:false,radar_verified:true}, other:{connected:true}})).toEqual({esps:2,radars:1});
 });
 it('does not count duplicate or missing bindings', () => {
  expect(connectionCounts(['a','a','b'], {a:{connected:true}})).toEqual({esps:1,radars:0});
  expect(connectionCounts(['a'], undefined)).toEqual({esps:0,radars:0});
 });
 it('counts an authenticated live ESP transport even before radar verification', () => {
  expect(connectionCounts(['a'], {a:{transport_online:true,connected:false,radar_verified:false}})).toEqual({esps:1,radars:0});
 });
});
