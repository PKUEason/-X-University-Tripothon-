"""Convert the supplied animated male/female FBX assets to self-contained web GLBs.
Usage: Blender -b --python art/character/import_designer_motion.py -- <extracted zip dir>
Keep the supplied skin and actions; remove root travel because campus code owns movement.
"""
import bpy, json, sys, math, argparse, hashlib, struct
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path)
parser.add_argument('--gender',choices=['male','female'])
parser.add_argument('--native-textures',action='store_true')
parser.add_argument('--output-name')
parser.add_argument('--report',default='designer-motion-report.json')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
source=args.source
if args.output_name and not args.gender:parser.error('--output-name requires --gender')
reports=[]
for gender,token in [('male','337953e8'),('female','a04d0240')]:
 if args.gender and gender!=args.gender:continue
 path=next(source.rglob('*'+token+'*.fbx'))
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.fbx(filepath=str(path))
 scene=bpy.context.scene
 rig=next(o for o in scene.objects if o.type=='ARMATURE')
 mesh=next(o for o in scene.objects if o.type=='MESH')
 original=list(bpy.data.actions)
 # Normalize the bind mesh together with its rig, preserving all skin matrices.
 rig.animation_data_clear()
 for b in rig.pose.bones:b.matrix_basis.identity()
 bpy.context.view_layer.update()
 points=[mesh.matrix_world@v.co for v in mesh.data.vertices]
 lo=Vector([min(p[i] for p in points) for i in range(3)])
 hi=Vector([max(p[i] for p in points) for i in range(3)])
 scale=1.78/(hi.z-lo.z)
 wrapper=bpy.data.objects.new('DesignerCharacter',None);scene.collection.objects.link(wrapper)
 for obj in list(scene.objects):
  if obj!=wrapper and obj.parent is None:obj.parent=wrapper
 wrapper.scale=(scale,)*3
 wrapper.location=(-((lo.x+hi.x)/2)*scale,-((lo.y+hi.y)/2)*scale,-lo.z*scale)
 for image in bpy.data.images:
  if image.size[0]:
   limit=2048 if 'basecolor' in image.name else 1024
   if not args.native_textures and max(image.size)>limit:image.scale(limit,limit)
   image.pack()
 hips=rig.pose.bones['mixamorig:Hips'];basis=hips.bone.matrix_local.to_3x3();inverse=basis.inverted()
 clips=[]
 names={'walk':'Walk','run':'Run','greet_01':'Greet','clap':'Clap','dance_04':'Dance'}
 for action in original:
  key=action.name.split('|')[-1];action.name=names[key]
  curves=action.layers[0].strips[0].channelbag(action.slots[0]).fcurves
  loc=[next(f for f in curves if f.data_path=='pose.bones["mixamorig:Hips"].location' and f.array_index==i) for i in range(3)]
  start,end=map(int,action.frame_range)
  first=basis@Vector([f.evaluate(start) for f in loc]);last=basis@Vector([f.evaluate(end) for f in loc]);delta=last-first
  # Subtract horizontal translation and starting offset in the bone's local basis.
  sampled={frame:Vector([f.evaluate(frame) for f in loc]) for frame in range(start,end+1)}
  for f in loc:f.keyframe_points.clear()
  for frame in range(start,end+1):
   t=(frame-start)/(end-start)
   world=first+delta*t;world.z=0
   correction=inverse@world
   for i,f in enumerate(loc):
    f.keyframe_points.insert(frame,sampled[frame][i]-correction[i],options={'FAST'})
  if key in ('walk','run'):
   for f in curves:
    a=f.evaluate(start)
    for p in f.keyframe_points:
     if p.co.x==end:p.co.y=a
  for f in curves:
   for p in f.keyframe_points:p.interpolation='LINEAR'
   f.update()
  action.use_fake_user=True
  clips.append({'name':action.name,'duration':(end-start)/scene.render.fps,'speed':math.hypot(delta.x,delta.y)*scale/((end-start)/scene.render.fps) if key in ('walk','run') else None})
 # No idle clip was supplied. Hold the relaxed opening pose of the greeting.
 greet=next(a for a in original if a.name=='Greet')
 rig.animation_data_create();rig.animation_data.action=greet;rig.animation_data.action_slot=greet.slots[0];scene.frame_set(1)
 pose={b.name:(b.location.copy(),b.rotation_quaternion.copy(),b.scale.copy()) for b in rig.pose.bones}
 rig.animation_data.action=None
 idle=bpy.data.actions.new('Idle');rig.animation_data.action=idle
 for frame in [1,49]:
  for bone in rig.pose.bones:
   bone.rotation_mode='QUATERNION';bone.location,bone.rotation_quaternion,bone.scale=pose[bone.name]
   for prop in ['location','rotation_quaternion','scale']:bone.keyframe_insert(data_path=prop,frame=frame,group=bone.name)
 idle.use_fake_user=True
 clips.append({'name':'Idle','duration':2,'speed':None})
 # Floor the relaxed pose, with a single shared rig/mesh transform.
 scene.frame_set(1);bpy.context.view_layer.update()
 deps=bpy.context.evaluated_depsgraph_get();evaluated=mesh.evaluated_get(deps);data=evaluated.to_mesh()
 floor=min((evaluated.matrix_world@v.co).z for v in data.vertices);evaluated.to_mesh_clear();wrapper.location.z-=floor
 scene['locomotionSpeed']={c['name']:c['speed'] for c in clips if c['speed'] is not None}
 source_sha=hashlib.sha256(path.read_bytes()).hexdigest()
 scene['sourceFBXSHA256']=source_sha
 scene['sourceImport']='fresh-zip-native-textures' if args.native_textures else 'designer-motion'
 out=ROOT/'public/assets'/(args.output_name or ('student-'+gender+'.glb'))
 scene.frame_start=1;scene.frame_end=329
 bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',export_extras=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=False,export_anim_slide_to_zero=True,export_image_format='AUTO' if args.native_textures else 'JPEG',export_jpeg_quality=88,export_yup=True)
 report={'gender':gender,'source':path.name,'source_sha256':source_sha,'output':out.name,'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'native_textures':args.native_textures,'height_m':1.78,'bones':len(rig.data.bones),'clips':clips,'bytes':out.stat().st_size,'front':'+Z','note':'Supplied rig and animations; in-place root correction; Idle holds the greeting opening pose.'}
 if args.native_textures:
  data=out.read_bytes();json_size=struct.unpack_from('<I',data,12)[0]
  gltf=json.loads(data[20:20+json_size]);binary=data[28+json_size:]
  originals={hashlib.sha256(f.read_bytes()).hexdigest():f.name for f in path.parent.rglob('*') if f.is_file()}
  embedded=[]
  for image in gltf['images']:
   view=gltf['bufferViews'][image['bufferView']];start=view.get('byteOffset',0)
   payload=binary[start:start+view['byteLength']];digest=hashlib.sha256(payload).hexdigest()
   embedded.append({'image':image.get('name'),'mime':image['mimeType'],'bytes':len(payload),'sha256':digest,'exact_zip_file':originals.get(digest)})
  report['embedded_images']=embedded
 reports.append(report);print('ASSET_REPORT',json.dumps(report))
(ROOT/'art/character'/args.report).write_text(json.dumps(reports,indent=2)+'\n')
