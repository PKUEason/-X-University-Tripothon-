"""Software raster preview of actual model triangles, not browser/WebGL validation."""
from pathlib import Path
import json,math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parent.parent
W,H=460,720
canvas=Image.new('RGB',(W*4,H+80),'#e6eadd');draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',19)
for panel,(gender,angle) in enumerate([('male',.35),('male',2.8),('female',.35),('female',2.8)]):
    eye=np.array([math.sin(angle)*3.8,1.2,-math.cos(angle)*3.8]);target=np.array([0,.89,0]);forward=(target-eye);forward/=np.linalg.norm(forward);right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    light=-forward+up*.8-right*.5;light/=np.linalg.norm(light)
    faces=[]
    for mesh in json.loads((root/'evidence'/f'student-{gender}.json').read_text()):
        p=np.array(mesh['position']).reshape(-1,3);normals=np.array(mesh['normal']).reshape(-1,3);rel=p-eye;z=np.sum(rel*forward,axis=1);xy=np.stack((W/2+(np.sum(rel*right,axis=1))*1420/z,H/2-(np.sum(rel*up,axis=1))*1420/z),axis=1)
        ids=np.array(mesh['index'] if mesh['index'] is not None else range(len(p))).reshape(-1,3)
        color=np.array([int(mesh['color'][i:i+2],16) for i in (1,3,5)])
        for ids3 in ids:
            pts=xy[ids3];normal=normals[ids3].mean(axis=0);length=np.linalg.norm(normal)
            if length<1e-8:continue
            normal/=length
            if normal@(-forward)<-.05:continue
            shade=.57+.43*max(0,normal@light)
            faces.append((float(z[ids3].mean()),pts,tuple((color*shade).clip(0,255).astype(int))))
    img=Image.new('RGB',(W,H),'#e6eadd');d=ImageDraw.Draw(img);d.ellipse((110,658,350,688),fill='#c4cebc')
    for _,pts,c in sorted(faces,key=lambda f:-f[0]):d.polygon([tuple(p) for p in pts],fill=c)
    canvas.paste(img,(panel*W,50));draw.text((panel*W+30,25),gender.upper()+(' / FRONT' if angle<1 else ' / BACK'),fill='#254839',font=font)
draw.text((30,H+45),'Actual mesh geometry / offline inspection / not a browser screenshot',fill='#52644f',font=font)
canvas.save(root/'evidence/student-geometry-preview.png')
