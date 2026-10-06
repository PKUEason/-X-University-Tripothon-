import * as THREE from 'three';
import {installBuildings} from './building-assets.js';
import {buildingStudies} from './building-studies.js';
import {installLibrary} from './library-asset.js';
import {createStudent} from './student.js';
import {GLTFLoader} from '../vendor/GLTFLoader.js';
import {createAtmosphere} from './atmosphere.js';
import {buildNeonCampus} from './neon-scene.js';
import {spaces,spaceAt,collisionBoxes,canWalk,routeTo,segmentClear,assetSlots} from './campus.js';
export function createWorld({container,position,profile,settings={},onSpace,onInteract,onArrive,onInfo,isBlocked,onNotice,onAssetStatus=()=>{}}){
 const scene=new THREE.Scene();scene.background=new THREE.Color('#69b9e8');scene.fog=new THREE.Fog('#69b9e8',85,230);
 const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.3));renderer.setSize(innerWidth,innerHeight);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.85;container.append(renderer.domElement);
 const camera=new THREE.PerspectiveCamera(58,innerWidth/innerHeight,.12,600);const ambient=new THREE.HemisphereLight(0xeaf4f8,0x6972a8,1.6);scene.add(ambient);
 const sun=new THREE.DirectionalLight(0xffecf4,2.8);sun.position.set(18,30,12);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-30,right:30,top:40,bottom:-40,near:1,far:110});sun.shadow.normalBias=.025;sun.shadow.bias=-.00018;sun.shadow.radius=2;sun.target.position.set(0,0,-10);scene.add(sun,sun.target);
 const art=buildNeonCampus(scene),slots=art.slots,atmosphere=createAtmosphere(scene,renderer);
 let inspectionBuilding='library'; const assetStates={};
 const assetStatus=(state,id='library')=>{assetStates[id]=state;if(id===inspectionBuilding)onAssetStatus(state);};
 installLibrary(scene,slots,assetStatus);installBuildings(scene,slots,assetStatus);
 const markers=Object.entries(spaces).filter(([,s])=>s.hotspot).map(([id,s])=>{const m=new THREE.Mesh(new THREE.TorusGeometry(.65,.04,8,36),new THREE.MeshBasicMaterial({color:0x59edff}));m.rotation.x=-Math.PI/2;m.position.set(s.hotspot[0],.075,s.hotspot[1]);scene.add(m);return {id,m};});
 const actor=new THREE.Group();scene.add(actor);actor.position.set(canWalk(position.x,position.z)?position.x:0,0,canWalk(position.x,position.z)?position.z:16);
 let navigationOpen=false,sceneWaiters=[],sceneTransition=null,navBlend=0,navYaw=0;let viewMode='third';let inspectionYaw=.28,inspectionPitch=.25,inspectionDistance=41,inspectionInside=false; let student=createStudent(profile);actor.add(student.root);
 const keys=new Set();let route=[],routeTarget=null,yaw=0,pitch=.04,distance=5,speed=1.2,drag=false,lastPointer,near=null,currentSpace=null,last=performance.now(),fpsTime=last,frames=0,routeUpdated=0;
 const canvas=renderer.domElement;canvas.tabIndex=0;canvas.setAttribute('aria-label','三维校园，WASD 移动，E 互动');
 const frameInspection=()=>{if(navBlend>.001)camera.setViewOffset(innerWidth,innerHeight,innerWidth*(innerWidth>=700?.25:.28)*navBlend,0,innerWidth,innerHeight);else if(viewMode==='library'&&innerWidth<700)camera.setViewOffset(innerWidth,innerHeight,0,innerHeight*.12,innerWidth,innerHeight);else camera.clearViewOffset();};
 const stop=()=>{keys.clear();drag=false;};
 const editing=()=>!!sceneTransition||navigationOpen||isBlocked()||!!document.activeElement?.closest('input,textarea,select,[contenteditable="true"]');
 const immersive=()=>['third','first'].includes(viewMode);
 let cursorMode=true,fallbackLook=false;
 const updateCursor=()=>{cursorMode=document.pointerLockElement!==canvas&&!fallbackLook;document.body.dataset.cursor=cursorMode?'ui':'scene';const hint=document.querySelector('#scene-control-hint');if(hint)hint.textContent=cursorMode?'点击场景开始环视 · Ctrl 切换光标':fallbackLook?'窗口内鼠标环视 · Ctrl 唤出光标 · M 导航':'移动鼠标环视 · Ctrl 唤出光标 · M 导航';};
 const releaseCursor=()=>{stop();fallbackLook=false;if(document.pointerLockElement===canvas)document.exitPointerLock?.();cursorMode=true;document.body.dataset.cursor='ui';const hint=document.querySelector('#scene-control-hint');if(hint)hint.textContent='点击场景开始环视 · Ctrl 切换光标';};
 const captureCursor=()=>{if(editing()||!immersive()||!cursorMode)return;canvas.focus({preventScroll:true});fallbackLook=true;updateCursor();if(!canvas.requestPointerLock)return;try{const pending=canvas.requestPointerLock();pending?.catch(()=>updateCursor());}catch{updateCursor();}};
 document.addEventListener('pointerlockchange',()=>{stop();fallbackLook=false;updateCursor();if(document.pointerLockElement===canvas&&editing())releaseCursor();});
 document.addEventListener('pointerlockerror',updateCursor);
 addEventListener('keydown',e=>{
  if(e.target?.closest?.('input,textarea,select,[contenteditable="true"]'))return;
  if((e.code==='ControlLeft'||e.code==='ControlRight')&&!e.repeat&&immersive()){e.preventDefault();if(cursorMode)captureCursor();else releaseCursor();return;}
  if(editing())return;
  const moving=['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code);
  if(moving&&viewMode==='library')return;
  if(moving)e.preventDefault();keys.add(e.code);
  if(e.code==='KeyE'&&!e.repeat&&near)onInteract(near);
 });
 addEventListener('keyup',e=>keys.delete(e.code));addEventListener('blur',releaseCursor);document.addEventListener('visibilitychange',()=>{if(document.hidden)releaseCursor();});document.addEventListener('focusin',()=>{if(editing())releaseCursor();});
 canvas.addEventListener('pointerdown',e=>{if(editing())return;if(immersive()&&e.pointerType!=='touch'){captureCursor();return;}drag=true;lastPointer={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);});
 canvas.addEventListener('pointermove',e=>{
  if(editing())return;
  const locked=document.pointerLockElement===canvas||fallbackLook;
  if(!locked&&!drag)return;
  const mx=locked?e.movementX:e.clientX-lastPointer.x,my=locked?e.movementY:e.clientY-lastPointer.y;
  if(viewMode==='library'){inspectionYaw-=mx*.004;inspectionPitch=THREE.MathUtils.clamp(inspectionPitch+my*.003,-.15,.9);}else{yaw-=mx*.004*(settings.sensitivity??1);pitch=THREE.MathUtils.clamp(pitch+my*.003*(settings.sensitivity??1),-.16,.75);}
  lastPointer={x:e.clientX,y:e.clientY};
 });
 canvas.addEventListener('pointerup',()=>drag=false);canvas.addEventListener('pointercancel',()=>drag=false);
 canvas.addEventListener('wheel',e=>{e.preventDefault();if(editing())return;const delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?innerHeight:1),scale=Math.exp(THREE.MathUtils.clamp(delta*.003,-1,1));if(viewMode==='library')inspectionDistance=THREE.MathUtils.clamp(inspectionDistance*scale,8,80);else distance=THREE.MathUtils.clamp(distance*scale,2.1,12);},{passive:false});
 for(const b of document.querySelectorAll('[data-move]')){b.onpointerdown=e=>{e.preventDefault();if(editing())return;keys.add(b.dataset.move);b.setPointerCapture(e.pointerId);};b.onpointerup=b.onpointercancel=()=>keys.delete(b.dataset.move);}
 const focus=new THREE.Vector3(),wanted=new THREE.Vector3();let orbitReach=5;
 const cameraObstacles=collisionBoxes.map(c=>new THREE.Box3(new THREE.Vector3(c.x-c.w-.15,0,c.z-c.d-.15),new THREE.Vector3(c.x+c.w+.15,c.h+.15,c.z+c.d+.15)));
 function safeReach(focus,ray,full){let reach=full;for(const bounds of cameraObstacles){const hit=new THREE.Ray(focus,ray).intersectBox(bounds,new THREE.Vector3());if(hit)reach=Math.min(reach,Math.max(.48,focus.distanceTo(hit)-.18));}return reach;}
 const routeLine=new THREE.Group();routeLine.name='navigation-route';scene.add(routeLine);
 const routeBackdrop=new THREE.MeshBasicMaterial({color:0x06517b,transparent:true,opacity:.8,depthWrite:false,side:THREE.DoubleSide});
 const routeMaterial=new THREE.MeshBasicMaterial({color:0x55ffff,transparent:true,opacity:.95,depthWrite:false,toneMapped:false,side:THREE.DoubleSide});
 let routeDistance=0;
 function guidanceTo(id){const end=spaces[id].hotspot||spaces[id].spawn;return segmentClear([actor.position.x,actor.position.z],end)?[[...end]]:[...routeTo(actor.position,id),[...end]];}
 function drawRoute(){
  for(const child of [...routeLine.children]){child.geometry.dispose();routeLine.remove(child);}
  const points=[[actor.position.x,actor.position.z],...route];routeDistance=0;
  for(let i=1;i<points.length;i++){
   const [x,z]=points[i-1],[tx,tz]=points[i],length=Math.hypot(tx-x,tz-z);routeDistance+=length;
   for(let d=0;d<length;d+=1.05){const segment=Math.min(.7,length-d),mid=d+segment/2;const dash=new THREE.Mesh(new THREE.PlaneGeometry(.12,segment),routeMaterial);dash.rotation.order='YXZ';dash.rotation.set(-Math.PI/2,Math.atan2(tx-x,tz-z),0);dash.position.set(x+(tx-x)*mid/length,.09,z+(tz-z)*mid/length);const border=new THREE.Mesh(new THREE.PlaneGeometry(.22,segment+.06),routeBackdrop);border.rotation.copy(dash.rotation);border.position.copy(dash.position);border.position.y-=.008;routeLine.add(border,dash);}
  }
  routeLine.visible=route.length>0;
 }
 function applySettings(value){settings={...settings,...value};document.body.dataset.reduceMotion=String(!!settings.reduceMotion);const high=settings.quality==='high',low=settings.quality==='performance';renderer.setPixelRatio(Math.min(devicePixelRatio,high?2:low?1:1.5));renderer.shadowMap.enabled=!low;const resolution=high?4096:2048;if(sun.shadow.mapSize.x!==resolution){sun.shadow.mapSize.set(resolution,resolution);sun.shadow.map?.dispose();sun.shadow.map=null;}renderer.setSize(innerWidth,innerHeight);atmosphere.configure(settings);}
 applySettings(settings);camera.position.set(actor.position.x,3,actor.position.z+5);
 function frame(now){requestAnimationFrame(frame);const dt=Math.min((now-last)/1000,.05);last=now;if(viewMode==='home'){frames=0;fpsTime=now;return;}navBlend=THREE.MathUtils.damp(navBlend,navigationOpen?1:0,6,dt);frameInspection();let dx=0,dz=0;const before=actor.position.clone();if(!editing()&&viewMode!=='library'){
 let f=Number(keys.has('KeyW')||keys.has('ArrowUp'))-Number(keys.has('KeyS')||keys.has('ArrowDown')),r=Number(keys.has('KeyD')||keys.has('ArrowRight'))-Number(keys.has('KeyA')||keys.has('ArrowLeft'));const len=Math.hypot(f,r)||1;f/=len;r/=len;dx=-Math.sin(yaw)*f+Math.cos(yaw)*r;dz=-Math.cos(yaw)*f-Math.sin(yaw)*r;
 const v=speed*(keys.has('ShiftLeft')||keys.has('ShiftRight')?1.65:1);
 const travel=v*dt;
 if(canWalk(actor.position.x+dx*travel,actor.position.z))actor.position.x+=dx*travel;
 if(canWalk(actor.position.x,actor.position.z+dz*travel))actor.position.z+=dz*travel;
 if(routeTarget){const dest=spaces[routeTarget];if(Math.hypot(actor.position.x-(dest.hotspot||dest.spawn)[0],actor.position.z-(dest.hotspot||dest.spawn)[1])<.65){const arrived=routeTarget;routeTarget=null;route=[];drawRoute();onArrive?.(arrived);}else if(now-routeUpdated>450){route=guidanceTo(routeTarget);drawRoute();routeUpdated=now;}}

 if(dx||dz){const angle=Math.atan2(-dx,-dz);actor.rotation.y+=Math.atan2(Math.sin(angle-actor.rotation.y),Math.cos(angle-actor.rotation.y))*Math.min(1,dt*12);}

 }
 const moving=before.distanceTo(actor.position)>.001;art.update(now*.001,settings.reduceMotion);student.update(dt,moving,keys.has('ShiftLeft')||keys.has('ShiftRight'),settings.reduceMotion,before.distanceTo(actor.position)/Math.max(dt,.000001));
 if(editing()&&!cursorMode)releaseCursor();
 if(viewMode==='library'){
 const study=buildingStudies[inspectionBuilding];
 if(inspectionInside){camera.position.fromArray(study.inside);camera.position.z-=(study.distance-inspectionDistance)*.18;camera.lookAt(study.look[0]+Math.sin(inspectionYaw)*8,study.look[1]-inspectionPitch*5,study.look[2]);}
 else{focus.fromArray(study.focus);const reach=inspectionDistance*Math.max(1,.8/camera.aspect);wanted.set(Math.sin(inspectionYaw)*reach,reach*Math.sin(inspectionPitch),Math.cos(inspectionYaw)*reach).add(focus);camera.position.lerp(wanted,1-Math.exp(-dt*5));camera.lookAt(focus);}
 }else if(viewMode==='overview'){
 camera.position.lerp(new THREE.Vector3(34,23,44),1-Math.exp(-dt*4));camera.lookAt(0,4,-9);
 }else if(viewMode==='first'){
 camera.position.copy(actor.position).add(new THREE.Vector3(0,1.67,0));camera.lookAt(camera.position.clone().add(new THREE.Vector3(-Math.sin(yaw),.12-pitch,-Math.cos(yaw))));
 }else{
 const reach=THREE.MathUtils.lerp(distance,2.9,navBlend),angle=yaw+Math.atan2(Math.sin(navYaw-yaw),Math.cos(navYaw-yaw))*navBlend;focus.copy(actor.position).add(new THREE.Vector3(.45*(1-navBlend),THREE.MathUtils.lerp(1.4,1.05,navBlend),0));wanted.set(Math.sin(angle)*reach,THREE.MathUtils.lerp(.35+pitch*reach,.12,navBlend),Math.cos(angle)*reach).add(focus);
 const ray=wanted.clone().sub(focus),full=ray.length();ray.normalize();const safe=safeReach(focus,ray,full);orbitReach=safe<orbitReach?safe:THREE.MathUtils.damp(orbitReach,safe,4,dt);wanted.copy(focus).addScaledVector(ray,orbitReach);camera.position.lerp(wanted,1-Math.exp(-dt*10));const actual=camera.position.clone().sub(focus),length=actual.length();actual.normalize();camera.position.copy(focus).addScaledVector(actual,safeReach(focus,actual,length));camera.lookAt(focus);
 }
 if(sceneTransition){
  sceneTransition.elapsed+=dt;const t=Math.min(1,sceneTransition.elapsed/1.15),ease=t*t*(3-2*t);
  camera.position.lerpVectors(sceneTransition.from,sceneTransition.to,settings.reduceMotion?1:ease);camera.lookAt(sceneTransition.focus);
  if(sceneTransition.elapsed>=1.45){sceneTransition=null;document.body.dataset.sceneTransition='false';if(!sceneWaiters.length)captureCursor();}
 }
 actor.visible=viewMode!=='first'&&viewMode!=='library';
 near=Object.keys(spaces).find(id=>{const s=spaces[id];return s.hotspot&&Math.hypot(s.hotspot[0]-actor.position.x,s.hotspot[1]-actor.position.z)<s.radius;})??null;
 const next=spaceAt(actor.position.x,actor.position.z);if(next!==currentSpace){currentSpace=next;onSpace(next);}
 markers.forEach(({m},i)=>m.scale.setScalar(settings.reduceMotion?1:1+Math.sin(now*.0015+i)*.025));routeLine.visible=route.length>0;routeMaterial.opacity=settings.reduceMotion?.95:.82+Math.sin(now*.003)*.15;const drawCalls=atmosphere.render(camera);frames++;if(!sceneTransition)for(const waiter of sceneWaiters.splice(0))waiter(true);
 if(now-fpsTime>500){onInfo({x:+actor.position.x.toFixed(2),z:+actor.position.z.toFixed(2),spaceId:currentSpace,near,fps:Math.round(frames*1000/(now-fpsTime)),drawCalls,character:student.root.userData.assetStatus==='ready'?'designer-rigged':'procedural',characterStatus:student.root.userData.assetStatus,motion:student.root.userData.motion,walking:moving,routeTarget,routeDistance,cursorMode,navigationOpen});frames=0;fpsTime=now;}
 }
 requestAnimationFrame(frame);addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();frameInspection();renderer.setSize(innerWidth,innerHeight);atmosphere.configure(settings);});canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();stop();onNotice('图形上下文已暂停，请刷新恢复。');});
 return {stop,releaseCursor,captureCursor,whenSceneReady(){return new Promise(resolve=>sceneWaiters.push(resolve));},setNavigationOpen(open){navigationOpen=open;stop();if(open){if(sceneTransition){sceneTransition=null;document.body.dataset.sceneTransition='false';for(const waiter of sceneWaiters.splice(0))waiter(false);}releaseCursor();navYaw=actor.rotation.y+Math.PI-.5;if(viewMode!=='third')viewMode='third';}frameInspection();},applySettings,setView(mode){const returning=viewMode==='home'&&mode==='third';
 if(sceneTransition){sceneTransition=null;document.body.dataset.sceneTransition='false';for(const waiter of sceneWaiters.splice(0))waiter(false);}
 if(returning){const aim=actor.position.clone().add(new THREE.Vector3(.45,1.4,0)),ray=new THREE.Vector3(Math.sin(yaw)*distance,.35+pitch*distance,Math.cos(yaw)*distance),full=ray.length();ray.normalize();const to=aim.clone().addScaledVector(ray,safeReach(aim,ray,full));sceneTransition={elapsed:0,focus:aim,to,from:to.clone().add(new THREE.Vector3(5,7,9))};camera.position.copy(sceneTransition.from);document.body.dataset.sceneTransition='true';}
 viewMode=['home','first','third','overview','library'].includes(mode)?mode:'third';frameInspection();stop();if(immersive())captureCursor();else releaseCursor();},setInspectionBuilding(id){if(!buildingStudies[id])return;inspectionBuilding=id;inspectionInside=false;inspectionYaw=.28;inspectionPitch=.25;inspectionDistance=buildingStudies[id].distance;onAssetStatus(assetStates[id]||'loading');},setInspectionPreset(preset){inspectionInside=preset==='inside';inspectionYaw=preset==='side'?1.25:preset==='front'?0:.28;inspectionPitch=preset==='inside'?0:.25;inspectionDistance=buildingStudies[inspectionBuilding].distance;},setNight(night){atmosphere.setNight(night);ambient.intensity=night?.35:1.6;scene.environmentIntensity=night?.25:1;scene.background.set(night?'#080d2b':'#69b9e8');scene.fog.color.copy(scene.background);sun.intensity=night?.45:2.8;renderer.toneMappingExposure=night?1:.85;},resetCamera(){yaw=0;pitch=.04;distance=5;},setStudent(profile){actor.remove(student.root);student.dispose();student=createStudent(profile);actor.add(student.root);},guideTo(id){if(!spaces[id]||spaces[id].locked)return;stop();route=guidanceTo(id);routeTarget=route.length?id:null;drawRoute();if(!route.length)onNotice('已在目的地附近，按 E 互动。');canvas.focus();captureCursor();},getNavigation:()=>({target:routeTarget,points:route.map(p=>[...p]),distance:routeDistance}),reset(){stop();route=[];routeTarget=null;drawRoute();actor.position.set(0,0,16);yaw=0;pitch=.04;currentSpace='gate';onSpace('gate');},getPosition:()=>({x:actor.position.x,z:actor.position.z}),async replaceAsset(spec){
 if(!assetSlots.some(s=>s.id===spec.id)||spec.format!=='glb'||!spec.url)throw Error('只接受清单中的 GLB slot');const loaded=await new GLTFLoader().loadAsync(spec.url);const model=loaded.scene;model.position.fromArray(spec.position);model.rotation.y=spec.rotationY;model.scale.setScalar(spec.scale);model.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});scene.add(model);const previous=slots.get(spec.id);if(previous)previous.visible=false;slots.set(spec.id,model);return model;
 }};
}
