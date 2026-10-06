"""Bind the supplied Tripo mesh and author in-place Idle / Walk / Run clips.
Blender 4.5. Input is a local FBX, supplied as -- <path>; no network or paid services.
Designer topology/UVs/textures are retained; the lower-leg bind pose is neutralized locally.
"""
import bpy, math, json, sys
from pathlib import Path
from mathutils import Vector, Quaternion
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'public/assets/student-rigged.glb'
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
source=Path(args[0]) if args else next((ROOT/'.local/designer-character').rglob('*.fbx'))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(source))
obj=next(o for o in bpy.data.objects if o.type=='MESH');obj.name='ExplorerMesh'
bpy.context.view_layer.objects.active=obj;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
vs=[v.co for v in obj.data.vertices];lo=Vector([min(v[i] for v in vs) for i in range(3)]);hi=Vector([max(v[i] for v in vs) for i in range(3)])
for v in obj.data.vertices:v.co=(v.co-Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z)))*(1.78/(hi.z-lo.z))
# Preserve detailed surface artwork but resize oversized input maps for a web character.
for image in bpy.data.images:
 if image.size[0]>0:
  limit=2048 if 'basecolor' in image.name else 1024
  if max(image.size)>limit:image.scale(limit,limit)
  image.pack()
for mat in obj.data.materials:
 bsdf=mat.node_tree.nodes.get('Principled BSDF')
 # The original metal map is retained; soften the over-strong imported normal relief.
 for n in mat.node_tree.nodes:
  if n.type=='NORMAL_MAP':n.inputs['Strength'].default_value=.65
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
# Classify connected shoe surfaces instead of splitting at x=0: the wide soles
# cross the centre line, and per-vertex signs wrongly bind their inner edges to
# the opposite leg (stretching a sole between both feet).
low={v.index for v in obj.data.vertices if v.co.z<.48};adj={i:[] for i in low};shoe_side={};finger_side={}
for e in obj.data.edges:
 a,b=e.vertices
 if a in low and b in low:adj[a].append(b);adj[b].append(a)
while low:
 todo=[low.pop()];part=[]
 while todo:
  i=todo.pop();part.append(i)
  for j in adj[i]:
   if j in low:low.remove(j);todo.append(j)
 centre=sum(obj.data.vertices[i].co.x for i in part)/len(part)
 side='L' if centre>0 else 'R'
 # The fingers hang beside the knees; a connected finger surface must never
 # enter the leg's analytic weights merely because it is below knee height.
 target=finger_side if abs(centre)>.18 and min(obj.data.vertices[i].co.z for i in part)>.28 else shoe_side
 for i in part:target[i]=side
# The supplied mesh is sculpted asymmetrically: one sole is already tipped
# upward in its bind pose. Calibrate each sole from its lower longitudinal
# envelope, rather than assuming identical foot bones imply level shoes.
def sole_calibration(side):
 points=[v.co.copy() for v in obj.data.vertices if v.co.z<.24 and shoe_side.get(v.index)==side]
 low=min(v.y for v in points);high=max(v.y for v in points);envelope=[]
 for i in range(1,9):
  band=[v for v in points if low+(high-low)*i/10<=v.y<=low+(high-low)*(i+1)/10]
  if band:envelope.append((sum(v.y for v in band)/len(band),min(v.z for v in band)))
 slopes=sorted((b[1]-a[1])/(b[0]-a[0]) for i,a in enumerate(envelope) for b in envelope[i+1:] if b[0]-a[0]>.04)
 return -math.atan(slopes[len(slopes)//2])
sole_pitch={side:sole_calibration(side) for side in ['L','R']}
sole_rot={side:Quaternion((1,0,0),sole_pitch[side]) for side in ['L','R']}
sole_floor={side:min((sole_rot[side]@v.co).z for v in obj.data.vertices if shoe_side.get(v.index)==side) for side in ['L','R']}
# Neutralize the sculpted shoe pitch in the bind mesh. Distribute the
# correction up the soft cuff/calf, fading out before the shorts. A permanent
# 29-degree animation offset otherwise folds the sock on every single step.
source_sole_pitch=sole_pitch.copy()
neutral={}
for side in ['L','R']:
 pivot=Vector((.095 if side=='L' else -.095,-.025,.27 if side=='L' else .32))
 rot=sole_rot[side]
 low=min((pivot+rot@(v.co-pivot)).z for v in obj.data.vertices if shoe_side.get(v.index)==side)
 neutral[side]=(pivot,rot,Vector((0,0,.023-low)))
for v in obj.data.vertices:
 side=shoe_side.get(v.index)
 if side is None:continue
 h=(sole_rot[side]@v.co).z-sole_floor[side]
 weight=1-smooth(.235,.43,h)
 pivot,rot,shift=neutral[side]
 v.co=v.co.lerp(pivot+rot@(v.co-pivot)+shift,weight)
sole_pitch={side:sole_calibration(side) for side in ['L','R']}
sole_rot={side:Quaternion((1,0,0),sole_pitch[side]) for side in ['L','R']}
sole_floor={side:min((sole_rot[side]@v.co).z for v in obj.data.vertices if shoe_side.get(v.index)==side) for side in ['L','R']}
bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='ExplorerRig';rig.data.name='ExplorerSkeleton'
bpy.ops.object.mode_set(mode='EDIT');rig.data.edit_bones.remove(rig.data.edit_bones[0])
bones={}
def bone(name,h,t,parent=None):
 b=rig.data.edit_bones.new(name);b.head=h;b.tail=t
 if parent:b.parent=bones[parent]
 bones[name]=b
bone('Hips',(0,0,.64),(0,0,.77))
bone('Spine',(0,0,.77),(0,0,.96),'Hips')
bone('Chest',(0,0,.96),(0,0,1.115),'Spine')
bone('Neck',(0,0,1.115),(0,0,1.23),'Chest')
bone('Head',(0,0,1.23),(0,0,1.65),'Neck')
for side,s in [('L',1),('R',-1)]:
 bone('UpperArm.'+side,(s*.19,0,1.08),(s*.24,-.015,.81),'Chest')
 bone('Forearm.'+side,(s*.24,-.015,.81),(s*.258,-.025,.565),'UpperArm.'+side)
 bone('Hand.'+side,(s*.258,-.025,.565),(s*.257,-.035,.42),'Forearm.'+side)
 # Fit the hinge to the ankle inside the cuff, not the middle of the sole.
 knee=(s*.104,-.025,.43);ankle=(s*.095,-.025,.27)
 bone('Thigh.'+side,(s*.104,0,.64),knee,'Hips')
 bone('Shin.'+side,knee,ankle,'Thigh.'+side)
 bone('Foot.'+side,ankle,Vector(ankle)+Vector((0,-.155,-.075)),'Shin.'+side)
bpy.ops.object.mode_set(mode='OBJECT')
# Heat weights follow surface connectivity around closely spaced fingers and shorts.
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
for m in obj.modifiers:
 # glTF uses linear blend skinning; keep source previews consistent with it.
 if m.type=='ARMATURE':m.use_deform_preserve_volume=False
# Stabilize rigid accessories, the stylized head and thick sneaker soles.
def set_weights(v,weights):
 for g in obj.vertex_groups:g.remove([v.index])
 for name,w in weights.items():
  if w>1e-5:obj.vertex_groups[name].add([v.index],w,'REPLACE')
for v in obj.data.vertices:
 x,y,z=v.co;s=shoe_side.get(v.index,'L' if x>=0 else 'R')
 if z>1.20:
  t=smooth(1.20,1.265,z);set_weights(v,{'Neck':1-t,'Head':t})
 elif y<-.17 and .64<z<1.115:set_weights(v,{'Chest':1})
 elif v.index in finger_side:set_weights(v,{'Hand.'+finger_side[v.index]:1})
 elif v.index in shoe_side:
  # Use height above each tilted sole, not a horizontal cut through its heel.
  # Keep the shoe rigid and spread ankle flexion through the soft sock/calf.
  h=(sole_rot[s]@v.co).z-sole_floor[s]
  t=smooth(.235,.335,h);knee=smooth(.385,.475,z)
  set_weights(v,{'Foot.'+s:1-t,'Shin.'+s:t*(1-knee),'Thigh.'+s:t*knee})
 # Keep a normalized, bounded four-weight skin for the web renderer.
 weights=sorted([(g.group,g.weight) for g in v.groups if g.weight>1e-5],key=lambda a:-a[1])[:4]
 if not weights:raise RuntimeError('Unweighted vertex')
 total=sum(w for _,w in weights)
 for g in obj.vertex_groups:g.remove([v.index])
 for index,w in weights:obj.vertex_groups[index].add([v.index],w/total,'REPLACE')
# Identity band is separate artwork: do not recolor skin, face or the supplied texture.
accent=bpy.data.materials.new('IdentityAccent');accent.diffuse_color=(.65,.8,1,1);accent.use_nodes=True
accent.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.65,.8,1,1)
accent.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.48
bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=(.225,-.092,.985));band=bpy.context.object;band.name='IdentityArmband';band.scale=(.035,.012,.043);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);band.data.materials.append(accent)
g=band.vertex_groups.new(name='UpperArm.L');g.add(list(range(len(band.data.vertices))),1,'REPLACE');m=band.modifiers.new('Arm binding','ARMATURE');m.object=rig;band.parent=rig
# Stable chest badge follows the chest and uses the same role color.
bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=10,location=(-.106,-.146,1.008));badge=bpy.context.object;badge.name='IdentityBadge';badge.scale=(.027,.008,.037);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);badge.data.materials.append(accent)
g=badge.vertex_groups.new(name='Chest');g.add(list(range(len(badge.data.vertices))),1,'REPLACE');m=badge.modifiers.new('Chest binding','ARMATURE');m.object=rig;badge.parent=rig
# Use actual bone animation tracks; clips contain no horizontal root displacement.
# Leg IK is solved analytically in the sagittal plane, keeping stance feet at floor level.
leg_rest={side:{'hip':rig.data.bones['Thigh.'+side].head_local.copy(),
 'ankle':rig.data.bones['Foot.'+side].head_local.copy(),
 'upper':rig.data.bones['Thigh.'+side].length,'lower':rig.data.bones['Shin.'+side].length} for side in ['L','R']}
def point_leg(side,foot_y,foot_z,hip_z):
 ref=leg_rest[side];hip=ref['hip']+Vector((0,0,hip_z));ankle=Vector((ref['ankle'].x,foot_y,ref['ankle'].z+foot_z));dvec=ankle-hip;d=dvec.length;l1=ref['upper'];l2=ref['lower']
 d=min(d,l1+l2-.001);a=(l1*l1-l2*l2+d*d)/(2*d);h=math.sqrt(max(0,l1*l1-a*a));unit=dvec.normalized();bend=Vector((0,unit.z,-unit.y))
 knee=hip+unit*a+bend*h
 return hip,knee,ankle
shoe_points={side:[v.co.copy()-leg_rest[side]['ankle'] for v in obj.data.vertices if shoe_side.get(v.index)==side and (sole_rot[side]@v.co).z-sole_floor[side]<.235] for side in ['L','R']}
def ankle_clearance(side,pitch=0):
 rot=Quaternion((1,0,0),pitch+sole_pitch[side])
 return -min((rot@v).z for v in shoe_points[side])
def walk_foot(q,side,running=False):
 if q<.5:
  fy=-.145+.58*q
  pitch=-.12*(1-smooth(0,.12,q))+.75*smooth(.32,.5,q)
  lift=0
 else:
  u=(q-.5)*2;blend=u*u*u*(10-15*u+6*u*u)
  # Match stance velocity AND acceleration at lift-off / contact. The small
  # overshoot is follow-through, avoiding a halt and reversal at each endpoint.
  fy=.145+.29*u-.58*blend;pitch=.75*(1-smooth(0,.45,u))-.12*smooth(.8,1,u);lift=math.sin(math.pi*u)**2*.035
 if running:fy*=1.25;lift*=2
 clearance=ankle_clearance(side,pitch)
 return fy,clearance+lift-leg_rest[side]['ankle'].z,pitch
scene=bpy.context.scene;scene.render.fps=60
for name,duration in [('Idle',180),('Walk',40),('Run',32)]:
 action=bpy.data.actions.new(name);rig.animation_data_create();rig.animation_data.action=action
 walk_samples=[]
 for frame in range(duration+1):
  t=frame/duration*math.tau
  for p in rig.pose.bones:p.rotation_mode='QUATERNION';p.rotation_quaternion=Quaternion();p.location=(0,0,0)
  if name!='Idle':
   # Follow the supporting leg's inverted-pendulum arc instead of crouching
   # throughout the cycle. A small loading dip softens each weight transfer.
   limits=[]
   for foot_side,offset in [('L',0),('R',.5)]:
    sy,sz,_=walk_foot((frame/duration+offset)%1,foot_side,name=='Run')
    ref=leg_rest[foot_side];reach=ref['upper']+ref['lower']-.0015
    limits.append(ref['ankle'].z+sz+math.sqrt(max(0,reach*reach-sy*sy))-.64)
   # A smooth minimum shares support continuously instead of switching legs
   # abruptly; the loading dip is periodic with no reset at the cycle seam.
   low=min(limits);softness=.002
   hip_z=low-softness*math.log(sum(math.exp(-(h-low)/softness) for h in limits))
   hip_z-=.003*((1+math.cos(t*2))*.5)**4
   if name=='Run':hip_z-=.012
  else:
   hip_z=min(ankle_clearance(side)+leg_rest[side]['upper']+leg_rest[side]['lower']-.002-.64 for side in ['L','R'])+math.sin(t)*.002
  rig.pose.bones['Hips'].location=(0,hip_z,0)
  for side,offset in [('L',0),('R',math.pi)]:
   phase=t+offset;q=(phase/math.tau)%1
   if name=='Idle':
    rig.pose.bones['UpperArm.'+side].rotation_quaternion=Quaternion((1,0,0),math.sin(phase)*.008)
   if name!='Idle':fy,fz,foot_pitch=walk_foot(q,side,name=='Run')
   elif name=='Idle':fy=0;fz=ankle_clearance(side)-leg_rest[side]['ankle'].z;foot_pitch=0
   hip,knee,ankle=point_leg(side,fy,fz,hip_z)
   desired={}
   foot_vector=Quaternion((1,0,0),foot_pitch+sole_pitch[side])@Vector((0,-.155,-.075))
   for n,vec in [('Thigh.'+side,knee-hip),('Shin.'+side,ankle-knee),('Foot.'+side,foot_vector)]:
    b=rig.data.bones[n];rest=b.matrix_local.to_quaternion();rest_dir=(b.tail_local-b.head_local).normalized();desired[n]=rest_dir.rotation_difference(vec.normalized())@rest
    parent=b.parent.name;parentq=desired.get(parent,rig.data.bones[parent].matrix_local.to_quaternion())
    rest_rel=rig.data.bones[parent].matrix_local.to_quaternion().inverted()@rest
    rig.pose.bones[n].rotation_quaternion=rest_rel.inverted()@parentq.inverted()@desired[n]
   if name!='Idle':
    arm_angle=.30*math.cos(phase) if name=='Walk' else -math.sin(phase)*.46
    rig.pose.bones['UpperArm.'+side].rotation_quaternion=Quaternion((1,0,0),arm_angle)
    rig.pose.bones['Forearm.'+side].rotation_quaternion=Quaternion((1,0,0),-.14-.08*max(0,-math.cos(phase)) if name=='Walk' else -.55)
  if name=='Walk':
   # Torso counter-rotation and slightly delayed head motion: the head follows
   # the body, with modest stabilization rather than a rigid lock or exaggerated bob.
   rig.pose.bones['Spine'].rotation_quaternion=Quaternion((1,0,0),.018+.01*math.cos(t*2))@Quaternion((0,1,0),.035*math.sin(t))
   rig.pose.bones['Chest'].rotation_quaternion=Quaternion((0,1,0),-.07*math.sin(t))@Quaternion((0,0,1),.012*math.sin(t))
   rig.pose.bones['Neck'].rotation_quaternion=Quaternion((1,0,0),-.008*math.cos(t*2-.35))
   rig.pose.bones['Head'].rotation_quaternion=Quaternion((1,0,0),.018*math.cos(t*2-.55))@Quaternion((0,1,0),.018*math.sin(t-.25))
  else:rig.pose.bones['Head'].rotation_quaternion=Quaternion((0,1,0),math.sin(t)*(.018 if name=='Idle' else .008))
  if name=='Walk':walk_samples.append({p.name:(p.rotation_quaternion.copy(),p.location.copy()) for p in rig.pose.bones})
  for p in rig.pose.bones:
   p.keyframe_insert('rotation_quaternion',frame=frame)
   if p.name=='Hips':p.keyframe_insert('location',frame=frame)
 if name=='Walk':
  # Circular, short-window pose filtering removes remaining IK/support-switch
  # kinks. Filtering the complete pose keeps limbs and body in phase, including
  # the last/first samples; it does not add a pause at the loop boundary.
  kernel=[1/16,4/16,6/16,4/16,1/16]
  for frame in range(duration+1):
   for p in rig.pose.bones:
    reference=walk_samples[frame%duration][p.name][0];parts=[0.,0.,0.,0.];loc=Vector()
    for delta,weight in zip(range(-2,3),kernel):
     q,v=walk_samples[(frame+delta)%duration][p.name];sign=1 if q.dot(reference)>=0 else -1
     for axis in range(4):parts[axis]+=q[axis]*weight*sign
     loc+=v*weight
    p.rotation_quaternion=Quaternion(parts).normalized();p.location=loc
    p.keyframe_insert('rotation_quaternion',frame=frame)
    if p.name=='Hips':p.keyframe_insert('location',frame=frame)
 # glTF NLA export: one named strip per clip.
 track=rig.animation_data.nla_tracks.new();track.name=name;track.strips.new(name,0,action);track.mute=True
rig.animation_data.action=None
for track in rig.animation_data.nla_tracks:track.mute=False
for p in rig.pose.bones:p.rotation_quaternion=Quaternion();p.location=(0,0,0)
scene.frame_set(0)
# Keep a self-contained editable source, including textures, rest rig, weights and actions.
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/character/explorer-rigged.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in (rig,obj,band,badge):o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_anim_slide_to_zero=True,export_image_format='AUTO',export_yup=True)
report={'source':source.name,'height_m':1.78,'bind_sole_correction_degrees':{side:math.degrees(v) for side,v in source_sole_pitch.items()},'sole_correction_degrees':{side:math.degrees(v) for side,v in sole_pitch.items()},'mesh_triangles':len(obj.data.polygons),'bones':len(rig.data.bones),'clips':[{'name':a.name,'frames':list(a.frame_range)} for a in bpy.data.actions],'max_influences':max(len(v.groups) for v in obj.data.vertices),'glb_bytes':OUT.stat().st_size,'note':'New authored rig and in-place motion; not the unavailable Tripo animation.'}
(ROOT/'art/character/asset-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
