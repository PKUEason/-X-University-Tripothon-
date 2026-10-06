"""Campus architectural assets. Blender 4.5; metre scale, exported glTF Y-up.
Run: blender -b --python art/campus/build_campus.py
Authoring scene remains editable; the web export is joined by material.
"""
import bpy, math, random, json, os
from mathutils import Vector
from pathlib import Path
random.seed(41)
ROOT = Path(__file__).resolve().parents[2]
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

# Assets use the same ceramic, brushed aluminium, low-iron glass and warm wood
# palette as Libpedia. World-space positions are supplied by the loader.
bronze=mat('Bronze | research sunshade',(.40,.25,.13),.74,.29)
labblue=mat('Equipment | deep teal',(.035,.15,.19),.35,.38)
screen=mat('Light | instrument screen',(.19,.65,.72),.2,.35,glow=.8)

def chair(x,y,z):
    box('Upholstered seat',(x,y+.49,z),(.62,.12,.59),felt,.07)
    box('Upholstered back',(x,y+.83,z+.24),(.61,.58,.10),felt,.05)
    for dx in [-.23,.23]:
        for dz in [-.21,.21]: tube('Chair leg',[(x+dx,y,z+dz),(x+dx,y+.45,z+dz)],.021,edge)

def table(x,y,z,w=2,d=1):
    box('Oak work surface',(x,y+.8,z),(w,.10,d),wood,.04)
    for dx in [-w*.4,w*.4]:
        for dz in [-d*.36,d*.36]: box('Desk leg',(x+dx,y+.38,z+dz),(.055,.76,.055),edge,.015)

def monitor(x,y,z):
    box('Display foot',(x,y+.85,z),(.30,.045,.20),edge,.015)
    box('Display stand',(x,y+1.02,z),(.04,.3,.045),edge,.009)
    box('Display enclosure',(x,y+1.24,z),(.77,.46,.055),structure,.027)
    box('Display glass',(x,y+1.24,z+.032),(.70,.39,.008),screen,.008)
    for i in range(4):box('Interface line',(x-.08,y+1.33-i*.065,z+.039),(.42-i*.07,.012,.003),ink,0)

def index_panel(x,z,number,title,subtitle,accent):
    box('Inset wayfinding panel',(x,2.14,z),(1.75,2.5,.12),structure,.055)
    text('Building number',number,(x,2.72,z+.07),.63,accent)
    text('Building index',title,(x,2.22,z+.07),.19)
    box('Index rule',(x,1.99,z+.074),(1.3,.015,.012),edge,.003)
    text('Building subtitle',subtitle,(x,1.76,z+.075),.10)
    text('Open access','OPEN / WELCOME',(x,1.34,z+.075),.09,accent)

def hall_shell(height,accent):
    # Walls coincide with existing campus collision planes x +/-4, z +/-5.
    box('Flush ground slab',(0,-.095,0),(8,.18,10),stone,.035)
    for x in [-4,4]:
        box('Side plinth',(x,.2,0),(.2,.4,10),porcelain,.04)
        box('Ground side glazing',(x,2.48,0),(.048,4.25,9.7),glass,.004)
        for z in [-4.9,-2.5,0,2.5,4.9]:
            box('Side mullion',(x,2.55,z),(.16,5.1,.10),edge,.012)
    box('Solid service wall',(0,2.5,-5),(8,5,.18),porcelain,.025)
    for x in [-2.83,2.83]:
        box('Front wing glazing',(x,2.42,5),(2.30,4.68,.055),glass,.005)
        box('Front reveal',(x,4.87,5.02),(2.3,.19,.22),porcelain,.02)
    for x in [-3.94,-1.63,1.63,3.94]:
        box('Door jamb',(x,2.47,5.05),(.13,4.94,.20),edge,.015)
    # Doors slide fully into side wings; no invisible obstacle across the entry.
    for x in [-2.08,2.08]:
        box('Sliding door parked',(x,1.70,4.87),(.76,3.38,.04),glass,.003)
        tube('Door pull',[(x,1.3,4.93),(x,2.1,4.93)],.021,edge)
    box('Door operator',(0,3.54,4.92),(3.2,.16,.25),structure,.025)
    box('Entry lintel light',(0,3.43,4.99),(3,.022,.03),warm,.004)
    box('Cantilever canopy',(0,3.78,5.35),(4.8,.20,1.55),porcelain,.055)
    for x in [-2.3,2.3]:tube('Canopy tension rod',[(x,3.84,5.98),(x,4.75,4.99)],.023,edge)
    for z in [4.8,5.7]:box('Canopy soffit light',(0,3.67,z),(4.15,.02,.025),warm,.002)
    for z in [-3,-1,1,3]:
        box('Ceiling baffle',(0,4.65,z),(7.7,.23,.13),wood,.018)
        box('Hall luminaire',(0,4.50,z),(5.7,.024,.05),warm,.005)
    for x in [-3.88,3.88]:box('Corner spine',(x,height/2,-4.86),(.3,height,.30),structure,.035)
    index_panel(-2.84,5.10,'03' if height>10 else '04','PROFESSOR' if height>10 else 'X LAB','DISCUSS / DEFINE' if height>10 else 'MAKE / TEST',accent)

def professor():
    hall_shell(17.1,rose)
    # Four inhabited storeys, visible floor edges and recessed ribbon glazing.
    for level,y in enumerate([4.96,8.65,12.34,16.03]):
        box('Structural floor',(0,y,0),(8.35,.27,10.3),porcelain,.065)
        box('Floor shadow reveal',(0,y-.19,0),(8.03,.10,10.01),structure,.018)
        if level==3:continue
        for z in [-4.91,4.91]:
            box('Upper ribbon glazing',(0,y+1.74,z),(7.78,3.13,.044),glass,.002)
            for x in [-3.75,-2.5,-1.25,0,1.25,2.5,3.75]:box('Facade mullion',(x,y+1.74,z),(.07,3.14,.14),edge,.009)
        for x in [-3.91,3.91]:
            box('Upper side glazing',(x,y+1.74,0),(.05,3.13,9.75),glass,.002)
            for z in [-3.7,-2.45,-1.2,0,1.2,2.45,3.7]:box('Side mullion',(x,y+1.74,z),(.14,3.13,.07),edge,.008)
        for x in [-2.5,1.8]:
            table(x,y+.15,2.1,1.8,.9);monitor(x,y+.15,1.98);chair(x,y+.15,3.1)
        table(0,y+.15,-2,3,1.5)
        for x in [-1,1]:chair(x,y+.15,-.9)
        box('Meeting room glass partition',(0,y+1.5,-.3),(7.4,2.6,.025),frit,.001)
        box('Core wall',(2.9,y+1.7,-4),(.15,3.2,1.75),wood,.025)
    # Sunshade blades cast narrow shadows and break the previous flat box facade.
    for x in [-3.85,-3.25,3.25,3.85]:
        box('Bronze vertical sunshade',(x,10.63,5.14),(.105,10.8,.5),bronze,.018)
        for y in [5.4,8.9,12.6,15.7]:box('Sunshade bracket',(x,y,4.97),(.22,.08,.38),edge,.01)
    for y in [6.0,9.65,13.34]:
        for i in range(4):box('Horizontal solar louvre',(0,y+i*.17,5.14),(5.8,.055,.5),edge,.012)
    box('Roof cornice',(0,16.32,0),(8.6,.24,10.55),porcelain,.08)
    for x in [-4.04,4.04]:
        box('Rooftop glass balustrade',(x,16.94,0),(.035,1.1,10.1),frit,.002)
        tube('Balustrade handrail',[(x,17.5,-5),(x,17.5,5)],.032,edge)
    box('Roof mechanical core',(0,17.0,-2),(3.5,1.25,3),structure,.07)
    for x in [-1.5,-.9,-.3,.3,.9,1.5]:box('Ventilation fin',(x,17.15,-.47),(.08,.78,.13),edge,.01)
    for x in [-2.9,2.9]:
        box('Terrace planter',(x,16.63,2.2),(1.4,.45,3),porcelain,.06)
        box('Terrace planting',(x,16.92,2.2),(1.12,.18,2.7),leaf,.08)
    box('Crown sign backing',(0,18.15,-1.75),(7.1,1.08,.26),structure,.08)
    text('Research tower sign','PROFESSOR',(0,17.91,-1.58),.66)
    box('Crown sign accent',(0,18.69,-1.56),(6.7,.032,.035),rose,.006)
    text('Entrance title','RESEARCH COMMONS',(0,4.17,5.14),.29)
    table(-1,0,-2.7,3,1.25);monitor(-1,0,-3.0)
    box('Discussion board',(0,2.5,-4.84),(4.8,1.75,.05),wood,.03)
    text('Discussion question','WHAT IF?',(0,2.65,-4.80),.48)
    text('Discussion prompt','ASK. LISTEN. CONNECT.',(0,2.15,-4.80),.17)

def lab():
    hall_shell(6.65,cyan)
    box('Laboratory ceiling',(0,5.02,0),(8.3,.28,10.3),porcelain,.065)
    box('Upper service ribbon',(0,5.77,0),(7.8,1.18,9.8),structure,.045)
    for x in [-3.94,3.94]:
        for z in [i*.28-4.4 for i in range(32)]:box('Service louvre',(x,5.8,z),(.15,.75,.065),edge,.01)
    for z in [-4.93,4.93]:
        box('Clerestory glazing',(0,5.86,z),(7.7,.84,.04),frit,.002)
        for x in range(-3,4):box('Clerestory mullion',(x,5.86,z),(.05,.9,.13),edge,.006)
    box('Roof folded edge',(0,6.55,0),(8.55,.33,10.5),porcelain,.09)
    box('Roof underside accent',(0,6.34,5.21),(8,.028,.035),cyan,.006)
    disc('Observatory drum',3.45,7.15,1.0,structure)
    for i in range(48):
        a=i*math.pi/24
        box('Drum radial vent',(3.47*math.cos(a),7.17,3.47*math.sin(a)),(.08,.6,.08),edge,.01)
    ring('Dome track lower',3.51,6.80,edge,.07);ring('Dome luminous equator',3.51,7.57,cyan,.035)
    # Segmented ellipsoidal roof, alternating metal cassettes and glass skylight.
    for i in range(32):
        a=i*math.pi/16;b=(i+1)*math.pi/16
        for j in range(6):
            lo=j*math.pi/12;hi=(j+1)*math.pi/12
            verts=[(3.4*math.cos(t)*math.cos(p),7.65+3.7*math.sin(t),3.4*math.cos(t)*math.sin(p)) for t,p in [(lo,a),(lo,b),(hi,b),(hi,a)]]
            mesh('Dome cassette',verts,[(0,3,2,1)],frit if i in [6,7,8,9] else porcelain)
        tube('Standing dome seam',[(3.42*math.cos(j*math.pi/48)*math.cos(a),7.65+3.72*math.sin(j*math.pi/48),3.42*math.cos(j*math.pi/48)*math.sin(a)) for j in range(25)],.022,edge)
    for j in [2,4]:
        t=j*math.pi/12;ring('Horizontal dome joint',3.405*math.cos(t),7.65+3.705*math.sin(t),edge,.018)
    disc('Dome cap',.30,11.37,.14,edge)
    text('Lab fascia','X LAB',(0,5.66,5.10),.61)
    text('Lab entrance title','PROTOTYPE / TEST / REPEAT',(0,4.2,5.12),.24)
    # Maker bench occupies exactly the old desk collision footprint.
    table(-1,0,-2.7,3,1.25)
    box('Instrument cabinet',(-1,.38,-2.7),(2.6,.70,1.08),labblue,.05)
    for x in [-1.8,-1,-.2]:
        box('Cabinet drawer',(x,.48,-2.12),(.72,.36,.035),edge,.022)
        box('Drawer pull',(x,.56,-2.08),(.25,.023,.034),structure,.008)
    monitor(-1.8,0,-2.95)
    for x in [-.72,.22]:
        for z in [-3.0,-2.25]:box('Printer gantry',(x,1.35,z),(.045,.97,.045),edge,.01)
    box('Printer top',(-.25,1.86,-2.63),(1.04,.10,.86),labblue,.025)
    box('Printer build plate',(-.25,1.01,-2.63),(.91,.08,.72),structure,.012)
    disc('Printed prototype',.19,1.2,.32,porcelain,rt=.11,cx=-.25,cz=-2.63)
    tube('Printer extrusion rail',[(-.65,1.7,-2.65),(.16,1.7,-2.65)],.028,edge)
    box('Extruder head',(-.25,1.62,-2.65),(.17,.22,.16),bronze,.02)
    box('Equipment wall rail',(0,2.6,-4.82),(6,1.8,.08),structure,.04)
    for x in range(-2,3):
        for y in [2,2.35,2.7,3.05]:disc('Equipment mounting point',.026,y,.03,edge,cx=x,cz=-4.75)
    text('Lab backwall','MAKE SOMETHING REAL',(0,3.7,-4.82),.34,structure)

def gate():
    for x in [-5,5]:
        box('Pier foundation',(x,.10,0),(2.18,.2,2.18),stone,.06)
        box('Pier core',(x,3.16,0),(1.83,6.15,1.82),structure,.10)
        for y in [.75,2.25,3.75,5.25]:
            for side in [-1,1]:box('Ceramic pier cassette',(x+side*.98,y,0),(.13,1.44,1.91),porcelain,.035)
        for xx in [x-.81,x+.81]:
            box('Pier vertical channel',(xx,3.12,1.015),(.085,5.92,.08),edge,.015)
            box('Recessed light blade',(xx,3.12,1.062),(.025,5.72,.016),cyan if x<0 else rose,.004)
        box('Pier capital',(x,6.26,0),(2.32,.30,2.25),porcelain,.08)
        index_panel(x,1.035,'X','UNIVERSITY','STAY CURIOUS',cyan if x<0 else rose)
        for yy in [.42,5.83]:
            for xx in [x-.64,x+.64]:
                bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=.045,location=xyz((xx,yy,1.075)));finish(bpy.context.object,'Flush fastener',edge)
    box('Portal box beam',(0,6.17,0),(12.1,.65,1.95),porcelain,.11)
    box('Portal shadow joint',(0,5.80,0),(11.6,.09,1.8),structure,.025)
    box('Canopy perimeter',(0,6.56,0),(12.35,.14,2.7),edge,.045)
    for x in [i*.38-5.7 for i in range(31)]:box('Portal ceiling slat',(x,5.70,0),(.105,.16,2.05),wood,.015)
    box('Welcome wash',(0,5.65,.68),(7.6,.025,.045),warm,.004)
    box('Sign recess',(0,6.16,1.01),(8.15,.56,.055),structure,.03)
    text('Portal title','X UNIVERSITY',(0,5.98,1.06),.46)
    text('Portal reverse title','STAY CURIOUS',(0,6.0,-1.025),.43).rotation_euler=(math.pi/2,0,math.pi)
    for x in [-3.5,-2.5,2.5,3.5]:box('Inset welcome marker',(x,.019,0),(.025,.026,2.5),edge,.003)

# Save each source before batching. Short-range vertex AO gives creases/contact
# depth without relying on an expensive runtime screen-space pass.
def export(name,build,position):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    build();scene=bpy.context.scene;scene.unit_settings.system='METRIC'
    scene['navigation_contract']='Metres; Y-up glTF; level access; existing collision envelope retained'
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'art/campus/{name}.blend'),compress=True)
    authored=len(scene.objects)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.convert(target='MESH')
    groups={}
    for o in list(scene.objects):
        if o.type=='MESH':groups.setdefault(o.data.materials[0].name,[]).append(o)
    for name_m,objects in groups.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in objects:o.select_set(True)
        bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();bpy.context.object.name=name_m
    from mathutils.bvhtree import BVHTree
    solid=[o for o in scene.objects if not o.data.materials[0].name.startswith(('Glazing','Light'))]
    verts=[];faces=[]
    for o in solid:
        offset=len(verts);verts.extend([o.matrix_world@v.co for v in o.data.vertices]);faces.extend([tuple(offset+i for i in p.vertices) for p in o.data.polygons])
    bvh=BVHTree.FromPolygons(verts,faces)
    for o in solid:
        d=o.data;normal_matrix=o.matrix_world.to_3x3().inverted().transposed();colors=d.color_attributes.new(name='ArchitecturalAO',type='FLOAT_COLOR',domain='POINT');d.color_attributes.active_color=colors
        for v,c in zip(d.vertices,colors.data):
            n=(normal_matrix@v.normal).normalized();origin=o.matrix_world@v.co+n*.015
            tangent=n.cross(Vector((0,0,1)) if abs(n.z)<.9 else Vector((0,1,0))).normalized();bitangent=n.cross(tangent);occlusion=0
            for k in range(6):
                a=k*2.399963;rr=math.sqrt((k+.5)/6);zz=math.sqrt(1-rr*rr)
                ray=(tangent*(math.cos(a)*rr)+bitangent*(math.sin(a)*rr)+n*zz).normalized()
                hit,_,_,distance=bvh.ray_cast(origin,ray,.85)
                if hit is not None:occlusion+=max(0,1-distance/.85)
            shade=1-.60*occlusion/6;c.color=(shade,shade,shade,1)
    out=ROOT/f'public/assets/{name}-refined.glb'
    bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',export_apply=True,export_yup=True,export_animations=False,export_cameras=False,export_lights=False)
    report={'asset':out.name,'bytes':out.stat().st_size,'triangles':sum(len(p.vertices)-2 for o in scene.objects for p in o.data.polygons),'drawMeshes':len(groups),'authoredObjects':authored,'position':position,'source':f'art/campus/{name}.blend'}
    print('ASSET_REPORT',json.dumps(report),flush=True);return report
reports=[export('professor',professor,[-15,0,0]),export('lab',lab,[15,0,0]),export('gate',gate,[0,0,12])]
(ROOT/'art/campus/asset-report.json').write_text(json.dumps(reports,indent=2)+'\n')
