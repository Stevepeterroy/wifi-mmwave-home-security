import {describe, expect, it} from 'vitest';
import {initialConfig} from './domain';
import {recentRadarMapPoints} from './radarMapPreview';

const module = {...initialConfig.modules[0], id:'test', x:0, z:0, yaw:0};
const bounds = {minX:0, minZ:0, width:5, depth:5};
const point = {point_index:0, x_cm:100, y_cm:100, z_cm:0, velocity_cm_s:50};

describe('recent radar map preview', () => {
  it('holds a single radar reflection across empty reports, without inventing a group', () => {
    const nodes = {test:{connected:true, radar_verified:true, frames:[
      {sequence:1, received_at:100, reported_points:1, points:[point], preview_incomplete:false},
      {sequence:2, received_at:100.5, reported_points:0, points:[], preview_incomplete:false},
    ]}};
    expect(recentRadarMapPoints([module],nodes,102,bounds)).toEqual([
      {point:{x:1,z:1,height:1.2,velocity:0.5},ageSeconds:2},
    ]);
    expect(recentRadarMapPoints([module],nodes,111,bounds)).toHaveLength(1);
    expect(recentRadarMapPoints([module],nodes,112.1,bounds)).toEqual([]);
  });
  it('never displays a disconnected or out-of-plan reflection', () => {
    const frame = {sequence:1, received_at:100, reported_points:1, points:[point], preview_incomplete:false};
    expect(recentRadarMapPoints([module],{test:{connected:false,radar_verified:true,frames:[frame]}},100,bounds)).toEqual([]);
    expect(recentRadarMapPoints([module],{test:{connected:true,radar_verified:true,frames:[frame]}},100,{...bounds,width:0.5})).toEqual([]);
  });
  it('uses the latest in-plan report when a newer report is outside the scanned space', () => {
    const inside = {sequence:1, received_at:100, reported_points:1, points:[point], preview_incomplete:false};
    const outside = {sequence:2, received_at:101, reported_points:1, points:[{...point,x_cm:900}], preview_incomplete:false};
    expect(recentRadarMapPoints([module],{test:{connected:true,radar_verified:true,frames:[inside,outside]}},102,bounds)).toEqual([
      {point:{x:1,z:1,height:1.2,velocity:0.5},ageSeconds:2},
    ]);
  });
});
