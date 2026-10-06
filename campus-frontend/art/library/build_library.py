"""Libpedia architectural sample. Blender 4.5; metre scale, exported glTF Y-up.
Run: blender -b --python art/library/build_library.py
Authoring scene remains editable; the web export is joined by material.
"""
import bpy, math, random, json, os
from mathutils import Vector
from pathlib import Path
random.seed(41)
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'public/assets/library-refined.glb'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def xyz(p): return (p[0], -p[2], p[1])
def mat(name, rgb, metal=0, rough=.4, alpha=1, glow=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*rgb,alpha); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*rgb,alpha)
    p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
    p.inputs['Alpha'].default_value=alpha
    if alpha<1: m.surface_render_method='DITHERED'
    if glow:
        p.inputs['Emission Color'].default_value=(*rgb,1); p.inputs['Emission Strength'].default_value=glow
    return m
porcelain=mat('Porcelain | satin ceramic',(.78,.84,.87),.18,.32)
edge=mat('Aluminium | brushed edges',(.37,.48,.57),.82,.25)
structure=mat('Structure | midnight anodised',(.025,.063,.085),.65,.32)
stone=mat('Floor | warm limestone',(.63,.65,.61),.04,.82)
wood=mat('Oak | reading furniture',(.32,.18,.075),0,.66)
felt=mat('Upholstery | ocean textile',(.07,.24,.27),0,.91)
glass=mat('Glazing | low iron blue',(.15,.40,.48),.25,.15,.32)
frit=mat('Glazing | fritted upper panels',(.30,.56,.62),.32,.24,.48)
cyan=mat('Light | ice blue',(.20,.79,.94),.1,.28,glow=2)
rose=mat('Light | orchid',(.64,.22,.48),.1,.3,glow=1.8)
warm=mat('Light | reading 3000K',(.98,.70,.38),0,.5,glow=1.4)
ink=mat('Lettering | porcelain',(.89,.94,.98),.05,.4)
leaf=mat('Plant | eucalyptus',(.10,.28,.22),0,.8)
bookm=[mat('Book | '+str(i),c,0,.82) for i,c in enumerate([(.15,.29,.37),(.49,.21,.29),(.68,.48,.23),(.34,.43,.35),(.51,.51,.61)])]

def finish(o,name,m,bevel=0):
    o.name=name; o.data.materials.append(m)
    if bevel:
        mod=o.modifiers.new('Manufactured edge radius','BEVEL'); mod.width=bevel; mod.segments=3
        mod=o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL'); mod.keep_sharp=True
    return o

def box(name,p,size,m=porcelain,bevel=.035):
    x,y,z=p; w,h,d=[v/2 for v in size]
    verts=[(x+sx*w,y+sy*h,z+sz*d) for sx,sy,sz in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    o=mesh(name,verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)],m)
    # Keep the origin at the centre so authored furniture rotations are meaningful.
    for v in o.data.vertices: v.co-=Vector(xyz(p))
    o.location=xyz(p)
    if bevel:
        mod=o.modifiers.new('Manufactured edge radius','BEVEL'); mod.width=bevel; mod.segments=3
        mod=o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL'); mod.keep_sharp=True
    return o

def mesh(name,verts,faces,m):
    d=bpy.data.meshes.new(name); d.from_pydata([xyz(p) for p in verts],[],faces); d.update()
    o=bpy.data.objects.new(name,d); bpy.context.collection.objects.link(o); return finish(o,name,m)

def tube(name,points,r,m,segments=8):
    d=bpy.data.curves.new(name,'CURVE'); d.dimensions='3D'; d.resolution_u=1; d.bevel_depth=r; d.bevel_resolution=1; d.resolution_u=1
    s=d.splines.new('POLY'); s.points.add(len(points)-1)
    for v,p in zip(s.points,points): v.co=(*xyz(p),1)
    o=bpy.data.objects.new(name,d); bpy.context.collection.objects.link(o); return finish(o,name,m)

def ring(name,r,y,m,th=.035,start=0,end=2*math.pi,cx=0,cz=0):
    n=max(8,int((end-start)*20)); return tube(name,[(cx+r*math.cos(start+i/n*(end-start)),y,cz+r*math.sin(start+i/n*(end-start))) for i in range(n+1)],th,m)

def disc(name,r,y,h,m,rt=None,cx=0,cz=0):
    bpy.ops.mesh.primitive_cone_add(vertices=96,radius1=r,radius2=r if rt is None else rt,depth=h,location=xyz((cx,y,cz)))
    o=finish(bpy.context.object,name,m)
    for p in o.data.polygons: p.use_smooth=len(p.vertices)==4
    return o

def text(name,value,p,size,m=ink):
    d=bpy.data.curves.new(name,'FONT'); d.body=value; d.align_x='CENTER'; d.size=size; d.extrude=.008; d.bevel_depth=.002; d.resolution_u=6
    o=bpy.data.objects.new(name,d); bpy.context.collection.objects.link(o); o.location=xyz(p); o.rotation_euler=(math.pi/2,0,0); return finish(o,name,m)

# Rectangular reading pavilion: open central entrance, existing campus footprint.
box('Perimeter plinth',(0,-.08,0),(20.5,.26,26.4),edge,.12)
box('Limestone slab',(0,.015,0),(20,.08,26),stone,.08)
# Fine expansion joints, a quiet scale cue below the glass skin.
for x in range(-9,10,3): box('Stone joint',(x,.061,0),(.012,.004,25.7),edge,0)
for z in range(-12,13,3): box('Stone joint',(0,.062,z),(19.7,.004,.012),edge,0)
for sx in [-1,1]:
    box('Facade shadow reveal',(sx*9.96,.24,0),(.13,.38,25.8),structure,.02)
    for z in [-11.5+i*2.3 for i in range(11)]:
        # Real individual panes and independent frames, not an opaque wall.
        box('Side glazing',(sx*9.94,2.92,z),(.045,5.08,2.21),glass,0)
        box('Side mullion',(sx*10,2.95,z-1.13),(.11,5.9,.075),edge,.018)
        box('Side transom',(sx*10,2.05,z),(.09,.065,2.25),edge,.015)
    for z in [-11.6,-5.8,0,5.8,11.6]:
        box('Structural column',(sx*9.65,2.98,z),(.22,5.96,.26),porcelain,.035)
        box('Column foot',(sx*9.65,.22,z),(.35,.34,.39),edge,.04)
for z in [-13,13]:
    for x in ([-9.2,-7.7,-6.2,-4.7,4.7,6.2,7.7,9.2] if z>0 else [-9.3+i*1.55 for i in range(13)]):
        box('Front and rear panes',(x,2.96,z),(1.48,5.15,.04),glass,0)
        box('Facade mullion',(x-.77,2.93,z+.04),(.07,5.84,.13),edge,.016)
        box('Facade transom',(x,2.05,z+.05),(1.5,.065,.09),edge,.012)
    for x in [-9.8,-6.4,6.4,9.8]: box('Portal column',(x,2.97,z),(.26,5.94,.32),porcelain,.04)
for x in [-3.58,3.58]: box('Door return pane',(x,2.96,13),(.70,5.15,.04),glass,0)
# Roof is a thin cantilever sandwich with a recessed soffit and metal seam.
box('Roof recessed soffit',(0,5.82,0),(20.45,.14,26.5),structure,.10)
box('Roof floating ceramic cornice',(0,6.03,0),(21.1,.28,27.1),porcelain,.13)
box('Roof top bevel',(0,6.23,0),(20.7,.12,26.7),edge,.06)
for sx in [-1,1]:
    box('Recessed side lighting',(sx*10.24,5.84,0),(.025,.035,25.7),warm,.008)
box('Front cornice light',(0,5.84,13.29),(19.8,.035,.025),cyan,.008)
# Architectural entrance: open sliding doors recessed behind a deep canopy.
box('Entry canopy',(0,4.7,13.68),(7.35,.24,2.25),porcelain,.11)
box('Entry shadow',(0,4.53,13.65),(6.96,.08,2.06),structure,.025)
for x in [-3.24,3.24]:
    box('Entrance jamb',(x,2.22,13.08),(.22,4.45,.30),edge,.04)
    box('Door parked open',(x*1.22,2.10,13.0),(1.42,4.08,.075),glass,.025)
    box('Door handle',(x*1.06,1.46,13.10),(.035,.72,.07),edge,.018)
box('Entry header',(0,4.18,13.08),(6.6,.18,.35),structure,.03)
box('Entry linear light',(0,4.35,14.49),(6.4,.035,.03),warm,.012)
box('Sign backing',(0,5.2,13.08),(7.1,.83,.13),porcelain,.055)
text('Library signage','L I B P E D I A',(0,5.0,13.18),.56,structure)
text('Door subtitle','LIBRARY  /  KNOWLEDGE COMMONS',(0,3.80,13.30),.14)
# Access stays level; inset strips read as a threshold without a false staircase.
for z in [13.25,13.6,13.95,14.3]: box('Entrance threshold',(0,.055,z),(6.25,.04,.025),edge,.01)
for x in [-5.0,5.0]:
    box('Wayfinding pedestal',(x,.74,13.55),(.53,1.48,.45),structure,.10)
    box('Directory screen',(x,1.01,13.79),(.4,.72,.02),cyan,.015)
# Cone grows out of the pavilion: inhabitable floors, tapered glass cassettes,
# slender load-bearing ribs, and a closed metal crown. No solid blue cone.
def radius(y): return 8.6-(y-6.5)*.365
levels=[6.5,9.25,12,14.75,17.5,20.25]
for y in levels:
    r=radius(y)
    # Four ring surfaces with an open central well for the stair.
    vv=[]
    for yy,rr in [(y-.25,r-.13),(y-.03,r-.13),(y-.25,1.97),(y-.03,1.97)]:
        vv.extend([(rr*math.cos(i*2*math.pi/96),yy,rr*math.sin(i*2*math.pi/96)) for i in range(96)])
    ff=[]
    for i in range(96):
        j=(i+1)%96
        ff.extend([(i,j,j+96,i+96),(i+96,j+96,j+288,i+288),(i+192,i+288,j+288,j+192),(i,i+192,j+192,j)])
    mesh('Tower floor with stair well',vv,ff,porcelain)
    ring('Floor reveal',r+.005,y,structure,.052)
    ring('Balcony lip',r-.04,y+.08,edge,.043)
    if y in [6.5,14.75]: ring('Inset halo',r+.075,y-.04,rose if y==6.5 else cyan,.032)
    # Inhabited floor behind glazing: repeated reading desks, warm ceiling lamps.
    if y<19:
        for i in range(8):
            a=2*math.pi*i/8
            x,z=(r-1.35)*math.cos(a),(r-1.35)*math.sin(a)
            desk=box('Tower reading ledge',(x,y+.77,z),(1.15,.10,.55),wood,.045); desk.rotation_euler.z=-a
            tube('Tower lamp',[(x,y+1.0,z),(x,y+1.55,z)],.025,edge)
            disc('Tower lamp shade',.16,y+1.56,.045,warm,cx=x,cz=z)
for j in range(len(levels)-1):
    y0,y1=levels[j]+.16,levels[j+1]-.12
    r0,r1=radius(y0),radius(y1)
    for i in range(32):
        a0=2*math.pi*(i+.035)/32; a1=2*math.pi*(i+.965)/32
        v=[(r0*math.cos(a0),y0,r0*math.sin(a0)),(r0*math.cos(a1),y0,r0*math.sin(a1)),(r1*math.cos(a1),y1,r1*math.sin(a1)),(r1*math.cos(a0),y1,r1*math.sin(a0))]
        mesh('Tapered glazing cassette',v,[(0,3,2,1)],frit if (i+2*j)%11==0 else glass)
        # Horizontal frit band at head: dense, subtle lines instead of neon everywhere.
        if j<3:
            for d in [.12,.18,.24]:
                yy=y1-d; rr=radius(yy)+.018
                tube('Solar frit',[(rr*math.cos(a0),yy,rr*math.sin(a0)),(rr*math.cos(a1),yy,rr*math.sin(a1))],.009,edge)
for i in range(32):
    a=2*math.pi*i/32
    pts=[((radius(y)+.045)*math.cos(a),y,(radius(y)+.045)*math.sin(a)) for y in [6.45,20.4]]
    tube('Continuous structural rib',pts,.065 if i%4==0 else .028,porcelain if i%4==0 else edge)
# A continuous stair gives the visible tower floors a believable circulation core.
# The sample walkthrough is ground-floor only; upper stairs are visual architecture.
disc('Stair central spine',.24,13.3,13.7,edge)
for i in range(92):
    y=6.52+i*.15; a=i*.19
    tread=box('Helical stair tread',(1.05*math.cos(a),y,1.05*math.sin(a)),(1.64,.085,.44),wood,.025)
    tread.rotation_euler.z=-a
    if i%3==0:
        tube('Stair baluster',[(1.83*math.cos(a),y,1.83*math.sin(a)),(1.83*math.cos(a),y+1.04,1.83*math.sin(a))],.018,edge)
tube('Stair handrail',[(1.83*math.cos(i*.19),7.56+i*.15,1.83*math.sin(i*.19)) for i in range(92)],.038,edge)
# Faceted titanium crown and cap seams (closed roof, not a second floating cone).
rbase=radius(20.25)
for i in range(32):
    a,b=2*math.pi*i/32,2*math.pi*(i+1)/32
    verts=[(rbase*math.cos(a),20.25,rbase*math.sin(a)),(rbase*math.cos(b),20.25,rbase*math.sin(b)),(.06*math.cos(b),27.0,.06*math.sin(b)),(.06*math.cos(a),27,.06*math.sin(a))]
    mesh('Titanium crown panel',verts,[(0,3,2,1)],porcelain if i%4 else edge)
    tube('Crown standing seam',[verts[0],verts[3]],.021,edge)
ring('Crown drip edge',rbase+.06,20.25,edge,.075)
for yy in [22,24,26]:
    rr=rbase*(27-yy)/(27-20.25)
    ring('Crown panel joint',rr+.008,yy,edge,.012)
disc('Antenna finial',.025,27.36,.72,edge)
# Hall furniture matches the navigation collision footprint.
for z in [-9,-2,5]:
    box('Bookcase back',(-6,1.57,z),(5.2,3.12,.15),wood,.04)
    for x in [-8.6,-6,-3.4]: box('Bookcase upright',(x,1.6,z+.33),(.09,3.2,.72),wood,.02)
    for y in [.12,.86,1.60,2.34,3.12]:
        box('Bookcase shelf',(-6,y,z+.34),(5.28,.075,.77),wood,.02)
        if y>3: continue
        for i in range(26):
            x=-8.40+i*.187; h=random.uniform(.40,.62)
            box('Book spine',(x,y+.06+h/2,z+.44),(.12,h,.34),bookm[i%5],0)
            box('Spine mark',(x,y+.18,z+.616),(.085,.018,.004),ink,0)
    box('Reading table',(6,.83,z),(5.2,.12,2),wood,.075)
    for x in [3.7,8.3]: box('Table trestle',(x,.4,z),(.10,.80,1.65),edge,.04)
    for x in [4.25,6,7.75]:
        box('Open book',(x,.92,z),( .46,.04,.32),ink,.01)
        tube('Task lamp arm',[(x,1.00,z-.5),(x,1.48,z-.5),(x,1.5,z-.2)],.024,edge)
        box('Task lamp diffuser',(x,1.49,z-.18),(.36,.035,.11),warm,.01)
for z in [8,3,-4,-10]:
    for x in [4.2,7.8]:
        box('Reading chair seat',(x,.48,z+1.8),(.68,.11,.66),felt,.10)
        box('Reading chair back',(x,.86,z+2.07),(.68,.65,.12),felt,.07)
        for dx in [-.25,.25]:
            for dz in [-.23,.23]: tube('Chair foot',[(x+dx,0,z+1.8+dz),(x+dx,.44,z+1.8+dz)],.028,edge)
# Slatted ceiling exposes depth above the clear front; all strips cast shadows.
for z in [-11,-8,-5,-2,1,4,7,10]:
    box('Ceiling acoustic baffle',(0,5.48,z),(18.8,.30,.10),wood,.025)
    box('Linear ceiling luminaire',(0,5.29,z),(12.5,.025,.04),warm,.01)
text('Interior wall title','THE NEXT QUESTION',(0,3.3,-12.84),.57)
text('Interior wall subtitle','READ. CONNECT. DISCOVER.',(0,2.9,-12.83),.17,edge)
# A projecting knowledge index at the front-left, with modeled type and dividers.
box('Knowledge index',(-7.4,2.4,13.14),(2.7,3.25,.13),structure,.075)
text('Index heading','02 / LIBRARY',(-7.4,3.40,13.23),.23)
for i,t in enumerate(['01   DISCOVER','02   RESEARCH','03   CONNECT']):
    text('Index entry',t,(-7.4,2.9-i*.53,13.23),.17)
    box('Index divider',(-7.4,2.78-i*.53,13.24),(2.14,.014,.015),edge,.003)
text('Index footer','OPEN TO EVERY QUESTION',(-7.4,1.3,13.23),.10,cyan)
# Save editable high-level scene with descriptive object names and modifiers.
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.world.color=(.16,.20,.25)
scene['design']='Libpedia v1 / glass reading pavilion and tapered knowledge tower'
scene['coordinate_contract']='glTF Y-up; origin at library centre; campus translation (0,0,-25)'
scene['navigation_contract']='open central entry z=13, x +/-3; floor y=0; pavilion 20 x 26 m'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/library/libpedia.blend'),compress=True)
# Apply authoring modifiers, convert text and curves, batch opaque geometry by material.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.convert(target='MESH')
groups={}
for o in list(scene.objects):
    if o.type=='MESH': groups.setdefault(o.data.materials[0].name,[]).append(o)
for name,objects in groups.items():
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects: o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]; bpy.ops.object.join(); bpy.context.object.name=name
# Bake short-range ambient occlusion to vertices for contact depth without SSAO.
from mathutils.bvhtree import BVHTree
solid=[o for o in scene.objects if o.type=='MESH' and not o.data.materials[0].name.startswith(('Glazing','Light'))]
verts=[]; faces=[]
for o in solid:
    offset=len(verts); verts.extend([o.matrix_world @ v.co for v in o.data.vertices])
    faces.extend([tuple(offset+i for i in p.vertices) for p in o.data.polygons])
bvh=BVHTree.FromPolygons(verts,faces)
for o in solid:
    d=o.data; normal_matrix=o.matrix_world.to_3x3().inverted().transposed()
    colors=d.color_attributes.new(name='ArchitecturalAO',type='FLOAT_COLOR',domain='POINT')
    d.color_attributes.active_color=colors
    for v,c in zip(d.vertices,colors.data):
        n=(normal_matrix @ v.normal).normalized(); origin=o.matrix_world @ v.co+n*.018
        tangent=n.cross(Vector((0,0,1)) if abs(n.z)<.9 else Vector((0,1,0))).normalized(); bitangent=n.cross(tangent)
        occlusion=0
        for k in range(8):
            a=k*2.399963; rr=math.sqrt((k+.5)/8); zz=math.sqrt(1-rr*rr)
            ray=(tangent*(math.cos(a)*rr)+bitangent*(math.sin(a)*rr)+n*zz).normalized()
            hit,_,_,distance=bvh.ray_cast(origin,ray,1.1)
            if hit is not None: occlusion+=max(0,1-distance/1.1)
        shade=1-.64*occlusion/8; c.color=(shade,shade,shade,1)
print('Vertex AO complete',flush=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(OUT),export_format='GLB',export_apply=True,export_yup=True,export_animations=False,export_cameras=False,export_lights=False)
triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in scene.objects if o.type=='MESH')
report={'generator':'Blender '+bpy.app.version_string,'asset':OUT.name,'bytes':OUT.stat().st_size,'triangles':triangles,'drawMeshes':len(groups),'dimensionsMetres':[21.1,27.72,27.3],'origin':'centre of library, Y-up; place at 0,0,-25','source':'art/library/libpedia.blend','build':'art/library/build_library.py'}
(ROOT/'art/library/asset-report.json').write_text(json.dumps(report,indent=2)+'\n')
print('LIBPEDIA_REPORT',json.dumps(report))
