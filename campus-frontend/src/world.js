import * as THREE from 'three';
import {createStudent} from './student.js';
import {GLTFLoader} from '../vendor/GLTFLoader.js';
import {mergeGeometries} from '../vendor/BufferGeometryUtils.js';
import {spaces,spaceAt,collisionBoxes,canWalk,routeTo,assetSlots} from './campus.js';
export function createWorld({container,position,profile,settings={},onSpace,onInteract,onArrive,onInfo,isBlocked,onNotice}){
 const scene=new THREE.Scene();scene.background=new THREE.Color('#b8d6e2');scene.fog=new THREE.Fog('#b8d6e2',52,115);
 const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.3));renderer.setSize(innerWidth,innerHeight);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.03;container.append(renderer.domElement);
 const camera=new THREE.PerspectiveCamera(58,innerWidth/innerHeight,.16,125);scene.add(new THREE.HemisphereLight(0xeaf4f8,0x788460,1.65));
 const sun=new THREE.DirectionalLight(0xffe3bc,2.6);sun.position.set(18,30,12);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-30,right:30,top:40,bottom:-40,near:1,far:110});sun.shadow.normalBias=.025;sun.shadow.bias=-.00018;sun.shadow.radius=2;sun.target.position.set(0,0,-10);scene.add(sun,sun.target);
 const mat=(color,other={})=>new THREE.MeshStandardMaterial({color,roughness:.85,...other});
 const textureLoader=new THREE.TextureLoader();const floorTexture=textureLoader.load('./assets/wood_floor_diff_1k.jpg');floorTexture.colorSpace=THREE.SRGBColorSpace;floorTexture.wrapS=floorTexture.wrapT=THREE.RepeatWrapping;floorTexture.repeat.set(4,6);floorTexture.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
 const wood=mat('#b79c70'),plaster=mat('#eeeadb'),green=mat('#284b40'),brass=mat('#c7ac6d',{metalness:.3}),stone=mat('#b9bdb0'),leaves=mat('#728361');
 const batches=new Map();const slots=new Map();let active='campus';
 function shape(g,m,x,y,z){g.translate(x,y,z);const key=active;if(!batches.has(key))batches.set(key,new Map());const group=batches.get(key);if(!group.has(m))group.set(m,[]);group.get(m).push(g);}
 const box=(x,y,z,w,h,d,m=plaster)=>shape(new THREE.BoxGeometry(w,h,d),m,x,y,z);
 const cyl=(x,y,z,r,h,m)=>shape(new THREE.CylinderGeometry(r,r,h,16),m,x,y,z);
 box(0,-.2,-9,55,.4,68,mat('#7b9672'));box(0,-.025,-8,6,.06,53,stone);box(0,-.015,0,22,.06,12,stone);box(0,-.015,7.8,40,.06,3.6,stone);
 for(let z=18;z>-36;z-=2){box(0,.034,z,5.8,.016,.022,plaster);}
 for(let z=8;z>-12;z-=3)box(0,.047,z,.09,.018,.9,brass);
 for(const x of [-8,8])for(const z of [16,7,-8]){cyl(x,1.4,z,.13,2.8,wood);for(const [dx,dy,dz,r]of [[0,0,0,1.35],[-.7,-.2,.25,.85],[.65,.35,-.2,.9]])shape(new THREE.SphereGeometry(r,20,14),leaves,x+dx,3.6+dy,z+dz);cyl(x-.24,2.15,z,.075,1.4,wood);}
 for(const x of [-8,8]){box(x,.5,3,2,.9,.7,wood);box(x,.8,3.3,2,.7,.15,green);}
 // Garden edges, lamps and campus notice boards keep the central routes open.
 const flower=mat('#dba78b'),petal=mat('#dfc86d'),lamp=mat('#f9e5af',{emissive:'#f2ca80',emissiveIntensity:.35});
 for(const x of [-23,23])for(const z of [-24,-10,4,17]){box(x,.27,z,2.5,.55,4.5,plaster);for(let i=0;i<7;i++){const dz=(i-3)*.52;cyl(x+(i%2?-.55:.4),.65,z+dz,.12,.6,leaves);shape(new THREE.SphereGeometry(.16,12,8),i%2?flower:petal,x+(i%2?-.55:.4),1,z+dz);}}
 for(const x of [-4,4])for(const z of [17,8,-8]){cyl(x,1.2,z,.035,2.4,green);box(x,2.48,z,.3,.2,.3,lamp);box(x,2.65,z,.38,.06,.38,green);}
 const sculpture=new THREE.TorusKnotGeometry(.54,.10,96,12);sculpture.rotateX(.45);shape(sculpture,brass,-6,1.55,0);cyl(-6,.24,0,.82,.48,plaster);
 box(-6,.8,8,.12,1.6,.12,green);box(-6,1.6,8,1.6,1.05,.1,wood);
 active='gate-shell';box(-5,3,12,2,6,2);box(5,3,12,2,6,2);box(0,6.1,12,12,.5,2,green);box(0,5.5,12,8,.16,1,brass);
 active='library-shell';box(0,-.045,-25,20,.12,26,mat('#ede0c7',{map:floorTexture}));box(-10,3,-25,.4,6,26);box(10,3,-25,.4,6,26);box(0,3,-38,20,6,.4);box(-6.6,3,-12,6.8,6,.4);box(6.6,3,-12,6.8,6,.4);box(0,5.6,-12,20,.8,.6,green);
 for(let z=-14;z>-38;z-=4){box(0,5.8,z,20,.15,.3,wood);box(9.7,3,z,.1,5.4,.15,wood);}
 const bookMats=['#466c65','#a79d71','#b9816b','#d4c8a5'].map(c=>mat(c));
 for(const z of [-20,-27,-34]){box(-6,1.6,z,5.2,3.2,.8,wood);box(-6,1.6,z+.43,4.95,3,.03,green);for(let j=0;j<4;j++){box(-6,.2+j*.78,z+.6,5.3,.08,1,wood);for(let i=0;i<23;i++){box(-8.35+i*.21,.52+j*.78,z+.8,.16,.48+(i%3)*.06,.34,bookMats[i%4]);}}box(6,.9,z,5.2,.16,2,wood);for(const x of [3.6,8.4])box(x,.45,z,.12,.9,1.7,green);box(5,.99,z,.6,.03,.8,plaster);}
 active='campus';for(const [id,x] of [['office',-15],['lab',15]]){box(x,-.035,0,8,.1,10,stone);box(x-4,3.5,0,.4,7,10);box(x+4,3.5,0,.4,7,10);box(x,3.5,-5,8,7,.4);box(x-2.8,3.5,5,2.4,7,.4);box(x+2.8,3.5,5,2.4,7,.4);box(x,6.5,5,8,1,.4,green);box(x,.025,6,8,.04,.35,brass);}
 // Work areas stay along the rear walls, leaving a clear arrival space.
 for(const x of [-16,16]){box(x,.78,-2.7,3,.13,1.25,wood);for(const dx of [-1.25,1.25])box(x+dx,.39,-2.7,.1,.78,.8,green);box(x,1.27,-3.1,1.1,.65,.07,green);box(x,1.27,-3.055,.94,.5,.01,mat('#a5c9cb',{emissive:'#547b80',emissiveIntensity:.2}));box(x,.865,-2.5,.8,.025,.28,plaster);}
 for(let i=0;i<5;i++)box(-17.1+i*.24,.97,-2.55,.15,.32,.3,bookMats[i%4]);
 cyl(17,1.03,-2.4,.13,.4,brass);box(15,1,-2.4,.4,.25,.4,green);
 for(const [id,groups] of batches){const group=new THREE.Group();group.name=id;for(const [m,geos] of groups){const mesh=new THREE.Mesh(mergeGeometries(geos),m);mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);geos.forEach(g=>g.dispose());}scene.add(group);slots.set(id,group);}
 function sign(text,sub,x,y,z,w){const c=document.createElement('canvas');c.width=1024;c.height=256;const ctx=c.getContext('2d');ctx.fillStyle='#284b40';ctx.fillRect(0,0,1024,256);ctx.fillStyle='#eeeada';ctx.textAlign='center';ctx.font='500 66px sans-serif';ctx.fillText(text,512,114);ctx.font='26px sans-serif';ctx.fillText(sub,512,185);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,w/4),new THREE.MeshBasicMaterial({map:t,polygonOffset:true,polygonOffsetFactor:-1,polygonOffsetUnits:-1}));mesh.position.set(x,y,z);scene.add(mesh);}
 sign('X UNIVERSITY','01 / A QUESTION IS A BEGINNING',0,4.5,13.05,7);sign('THE LIBRARY','03 / KNOWLEDGE INTO QUESTIONS',0,4.7,-11.7,7);sign('PROFESSOR','04 / DEFINE YOUR QUESTION',-15,5.8,5.235,6);sign('X LAB','05 / BUILD YOUR PLAN',15,5.8,5.235,6);
 sign('PLAZA','02 / FOLLOW YOUR QUESTION',-6,1.6,8.07,1.55);
 const markers=Object.entries(spaces).filter(([,s])=>s.hotspot).map(([id,s])=>{const m=new THREE.Mesh(new THREE.TorusGeometry(.65,.04,8,36),new THREE.MeshBasicMaterial({color:0xd8b773}));m.rotation.x=-Math.PI/2;m.position.set(s.hotspot[0],.075,s.hotspot[1]);scene.add(m);return {id,m};});
 const actor=new THREE.Group();scene.add(actor);actor.position.set(canWalk(position.x,position.z)?position.x:0,0,canWalk(position.x,position.z)?position.z:16);
 const character='student';let student=createStudent(profile);actor.add(student.root);
 const keys=new Set();let route=[],routeTarget=null,yaw=0,pitch=.18,distance=5,speed=3.5,drag=false,lastPointer,near=null,currentSpace=spaceAt(actor.position.x,actor.position.z),last=performance.now(),fpsTime=last,frames=0,routeBlocked=0;
 const canvas=renderer.domElement;canvas.tabIndex=0;canvas.setAttribute('aria-label','三维校园，WASD 移动，E 互动');
 const stop=()=>{route=[];routeTarget=null;keys.clear();drag=false;};
 const editing=()=>isBlocked()||!!document.activeElement?.closest('input,textarea,select,[contenteditable="true"]');
 addEventListener('keydown',e=>{if(editing())return;const moving=['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code);if(moving){e.preventDefault();route=[];routeTarget=null;}keys.add(e.code);if(e.code==='KeyE'&&!e.repeat&&near)onInteract(near);});addEventListener('keyup',e=>keys.delete(e.code));addEventListener('blur',stop);document.addEventListener('visibilitychange',stop);document.addEventListener('focusin',()=>{if(editing())stop();});
 canvas.addEventListener('pointerdown',e=>{if(editing())return;drag=true;lastPointer={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);});canvas.addEventListener('pointermove',e=>{if(!drag)return;yaw-=(e.clientX-lastPointer.x)*.004*(settings.sensitivity??1);pitch=THREE.MathUtils.clamp(pitch+(e.clientY-lastPointer.y)*.003*(settings.sensitivity??1),.05,.75);lastPointer={x:e.clientX,y:e.clientY};});canvas.addEventListener('pointerup',()=>drag=false);canvas.addEventListener('pointercancel',()=>drag=false);canvas.addEventListener('wheel',e=>{e.preventDefault();if(!editing())distance=THREE.MathUtils.clamp(distance+e.deltaY*.003,2.5,7);},{passive:false});
 for(const b of document.querySelectorAll('[data-move]')){b.onpointerdown=e=>{e.preventDefault();if(editing())return;route=[];routeTarget=null;keys.add(b.dataset.move);b.setPointerCapture(e.pointerId);};b.onpointerup=b.onpointercancel=()=>keys.delete(b.dataset.move);}
 const focus=new THREE.Vector3(),wanted=new THREE.Vector3();let orbitReach=5;
 const cameraObstacles=collisionBoxes.map(c=>new THREE.Box3(new THREE.Vector3(c.x-c.w-.15,0,c.z-c.d-.15),new THREE.Vector3(c.x+c.w+.15,c.h+.15,c.z+c.d+.15)));
 function safeReach(focus,ray,full){let reach=full;for(const bounds of cameraObstacles){const hit=new THREE.Ray(focus,ray).intersectBox(bounds,new THREE.Vector3());if(hit)reach=Math.min(reach,Math.max(.48,focus.distanceTo(hit)-.18));}return reach;}
 const routeLine=new THREE.Line(new THREE.BufferGeometry(),new THREE.LineBasicMaterial({color:'#bd9246',transparent:true,opacity:.8,depthWrite:false}));routeLine.visible=false;scene.add(routeLine);
 function drawRoute(){routeLine.geometry.dispose();routeLine.geometry=new THREE.BufferGeometry().setFromPoints([actor.position.clone().setY(.06),...route.map(([x,z])=>new THREE.Vector3(x,.06,z))]);routeLine.visible=route.length>0;}
 function applySettings(value){settings={...settings,...value};const high=settings.quality==='high',low=settings.quality==='performance';renderer.setPixelRatio(Math.min(devicePixelRatio,high?2:low?1:1.5));renderer.shadowMap.enabled=!low;const resolution=high?4096:2048;if(sun.shadow.mapSize.x!==resolution){sun.shadow.mapSize.set(resolution,resolution);sun.shadow.map?.dispose();sun.shadow.map=null;}renderer.setSize(innerWidth,innerHeight);}
 applySettings(settings);camera.position.set(actor.position.x,3,actor.position.z+5);
 function frame(now){requestAnimationFrame(frame);const dt=Math.min((now-last)/1000,.05);last=now;let dx=0,dz=0,routeDistance=Infinity;const before=actor.position.clone();if(!editing()){
 let f=Number(keys.has('KeyW')||keys.has('ArrowUp'))-Number(keys.has('KeyS')||keys.has('ArrowDown')),r=Number(keys.has('KeyD')||keys.has('ArrowRight'))-Number(keys.has('KeyA')||keys.has('ArrowLeft'));const len=Math.hypot(f,r)||1;f/=len;r/=len;dx=-Math.sin(yaw)*f+Math.cos(yaw)*r;dz=-Math.cos(yaw)*f-Math.sin(yaw)*r;
 if(route.length){const [tx,tz]=route[0],rx=tx-actor.position.x,rz=tz-actor.position.z,rr=Math.hypot(rx,rz);routeDistance=rr;if(rr<.12){actor.position.x=tx;actor.position.z=tz;route.shift();drawRoute();dx=dz=0;if(!route.length&&routeTarget){const arrived=routeTarget;routeTarget=null;onArrive?.(arrived);}}else{dx=rx/rr;dz=rz/rr;}}
 const v=speed*(keys.has('ShiftLeft')||keys.has('ShiftRight')?1.65:1),travel=Math.min(v*dt,routeDistance);if(canWalk(actor.position.x+dx*travel,actor.position.z))actor.position.x+=dx*travel;if(canWalk(actor.position.x,actor.position.z+dz*travel))actor.position.z+=dz*travel;
 if(dx||dz){const angle=Math.atan2(-dx,-dz);actor.rotation.y+=Math.atan2(Math.sin(angle-actor.rotation.y),Math.cos(angle-actor.rotation.y))*Math.min(1,dt*12);}
 if(route.length&&before.distanceTo(actor.position)<.0001&&(dx||dz)){routeBlocked+=dt;if(routeBlocked>1){route=routeTarget?routeTo(actor.position,routeTarget):[];routeBlocked=0;if(!route.length){routeTarget=null;onNotice('暂时没有可通行路线，请稍微移动后重试。');}}}else routeBlocked=0;
 }
 const moving=before.distanceTo(actor.position)>.001;student.update(dt,moving,keys.has('ShiftLeft')||keys.has('ShiftRight'),settings.reduceMotion);
 focus.copy(actor.position).add(new THREE.Vector3(0,1.35,0));wanted.set(Math.sin(yaw)*distance,1.1+pitch*distance,Math.cos(yaw)*distance).add(focus);
 const ray=wanted.clone().sub(focus),full=ray.length();ray.normalize();const safe=safeReach(focus,ray,full);orbitReach=safe<orbitReach?safe:THREE.MathUtils.damp(orbitReach,safe,4,dt);wanted.copy(focus).addScaledVector(ray,orbitReach);camera.position.lerp(wanted,1-Math.exp(-dt*10));const actual=camera.position.clone().sub(focus),length=actual.length();actual.normalize();camera.position.copy(focus).addScaledVector(actual,safeReach(focus,actual,length));camera.lookAt(focus);
 near=Object.keys(spaces).find(id=>{const s=spaces[id];return s.hotspot&&Math.hypot(s.hotspot[0]-actor.position.x,s.hotspot[1]-actor.position.z)<s.radius;})??null;
 const next=spaceAt(actor.position.x,actor.position.z);if(next!==currentSpace){currentSpace=next;onSpace(next);}
 markers.forEach(({m},i)=>m.scale.setScalar(settings.reduceMotion?1:1+Math.sin(now*.0015+i)*.025));routeLine.visible=route.length>0;if(route.length){routeLine.geometry.attributes.position.setXYZ(0,actor.position.x,.06,actor.position.z);routeLine.geometry.attributes.position.needsUpdate=true;}renderer.render(scene,camera);frames++;
 if(now-fpsTime>500){onInfo({x:+actor.position.x.toFixed(2),z:+actor.position.z.toFixed(2),spaceId:currentSpace,near,fps:Math.round(frames*1000/(now-fpsTime)),drawCalls:renderer.info.render.calls,character,walking:route.length>0});frames=0;fpsTime=now;}
 }
 requestAnimationFrame(frame);addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);});canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();stop();onNotice('图形上下文已暂停，请刷新恢复。');});
 return {stop,applySettings,resetCamera(){yaw=0;pitch=.18;distance=5;},setStudent(profile){actor.remove(student.root);student.dispose();student=createStudent(profile);actor.add(student.root);},walkTo(id){if(!spaces[id]||spaces[id].locked)return;stop();if(Math.hypot(actor.position.x-spaces[id].spawn[0],actor.position.z-spaces[id].spawn[1])<.25){onArrive?.(id);return;}route=routeTo(actor.position,id);routeTarget=route.length?id:null;drawRoute();if(!route.length)onNotice('没有找到可通行路线。');canvas.focus();},reset(){stop();actor.position.set(0,0,16);yaw=0;pitch=.18;currentSpace='gate';onSpace('gate');},getPosition:()=>({x:actor.position.x,z:actor.position.z}),async replaceAsset(spec){
 if(!assetSlots.some(s=>s.id===spec.id)||spec.format!=='glb'||!spec.url)throw Error('只接受清单中的 GLB slot');const loaded=await new GLTFLoader().loadAsync(spec.url);const model=loaded.scene;model.position.fromArray(spec.position);model.rotation.y=spec.rotationY;model.scale.setScalar(spec.scale);model.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});scene.add(model);const previous=slots.get(spec.id);if(previous)previous.visible=false;slots.set(spec.id,model);return model;
 }};
}
