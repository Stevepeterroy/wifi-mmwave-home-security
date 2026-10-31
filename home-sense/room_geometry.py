"""Persisted room-outline validation and point membership in house metres."""
import math

def cross(a,b,c):return (b['x']-a['x'])*(c['z']-a['z'])-(b['z']-a['z'])*(c['x']-a['x'])
def on_segment(p,a,b):return abs(cross(a,b,p))<1e-8 and min(a['x'],b['x'])-1e-8<=p['x']<=max(a['x'],b['x'])+1e-8 and min(a['z'],b['z'])-1e-8<=p['z']<=max(a['z'],b['z'])+1e-8

def validate_boundary(room):
 points=room.get('boundary')
 if points is None:return
 if not isinstance(points,list) or not 3<=len(points)<=128:raise ValueError('Room boundary needs 3 to 128 points')
 for p in points:
  if not isinstance(p,dict) or any(not isinstance(p.get(k),(int,float)) or isinstance(p.get(k),bool) or not math.isfinite(p[k]) for k in ('x','z')):raise ValueError('Invalid room boundary point')
  if not room['x']-1e-6<=p['x']<=room['x']+room['width']+1e-6 or not room['z']-1e-6<=p['z']<=room['z']+room['depth']+1e-6:raise ValueError('Boundary point exceeds room extent')
 for i,a in enumerate(points):
  b=points[(i+1)%len(points)]
  if math.hypot(a['x']-b['x'],a['z']-b['z'])<.02:raise ValueError('Boundary points too close')
  for j in range(i+1,len(points)):
   if j==i+1 or (i==0 and j==len(points)-1):continue
   c,d=points[j],points[(j+1)%len(points)]
   if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0 or any((on_segment(c,a,b),on_segment(d,a,b),on_segment(a,c,d),on_segment(b,c,d))):raise ValueError('Room boundary intersects itself')
 area=abs(sum(p['x']*points[(i+1)%len(points)]['z']-points[(i+1)%len(points)]['x']*p['z'] for i,p in enumerate(points)))/2
 if area<.04:raise ValueError('Room boundary is too small')

def contains_point(point,room):
 if not all(isinstance(point.get(k),(int,float)) and math.isfinite(point[k]) for k in ('x','z')):return False
 points=room.get('boundary')
 if not points:return room['x']<=point['x']<room['x']+room['width'] and room['z']<=point['z']<room['z']+room['depth']
 inside=False
 for i,a in enumerate(points):
  b=points[(i+1)%len(points)]
  if on_segment(point,a,b):return True
  if (a['z']>point['z'])!=(b['z']>point['z']) and point['x']<(b['x']-a['x'])*(point['z']-a['z'])/(b['z']-a['z'])+a['x']:inside=not inside
 return inside

def reflection_in_room(p,module,room):
 try:
  x,y=float(p['x_cm'])/100,float(p['y_cm'])/100
  angle=math.radians(float(module['yaw']))
  point={'x':float(module['x'])+x*math.cos(angle)+y*math.sin(angle),'z':float(module['z'])-x*math.sin(angle)+y*math.cos(angle)}
  return contains_point(point,room)
 except (KeyError,ValueError,TypeError):return False
