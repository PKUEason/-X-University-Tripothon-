import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {Window} from 'happy-dom';
import {canWalk} from '../src/campus.js';
const root=new URL('../',import.meta.url).pathname;
const result=await build({entryPoints:[root+'src/world.js'],bundle:true,write:false,format:'iife',globalName:'WorldModule',plugins:[{name:'cpu-scene-harness',setup(build){build.onResolve({filter:/^\.\.\/vendor\//},args=>({path:root+'public/vendor/'+args.path.split('/').at(-1)}));build.onResolve({filter:/^three$/},()=>({path:'three-cpu',namespace:'fixture'}));build.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:`export * from ${JSON.stringify(root+'public/vendor/three.module.js')};import {Texture} from ${JSON.stringify(root+'public/vendor/three.module.js')};export class TextureLoader{load(){return new Texture();}}export class WebGLRenderer{constructor(){this.domElement=document.createElement('canvas');this.domElement.setPointerCapture=()=>{};this.shadowMap={};this.capabilities={getMaxAnisotropy:()=>8};this.info={render:{calls:0}};}setPixelRatio(){}setSize(){}render(scene,camera){window.__renderCount=(window.__renderCount||0)+1;window.__scene=scene;window.__camera=camera;}}`,resolveDir:root}));}}]});
function harness(position){const window=new Window();window.document.body.innerHTML='<main id="world"></main>';window.HTMLCanvasElement.prototype.getContext=()=>({fillRect(){},fillText(){}});let frame;window.requestAnimationFrame=fn=>{frame=fn;};window.eval(result.outputFiles[0].text);const visited=[],arrivals=[],notices=[];const world=window.WorldModule.createWorld({container:window.document.querySelector('#world'),position,profile:{gender:'female'},settings:{quality:'balanced'},onSpace:id=>visited.push(id),onInteract(){},onArrive:id=>arrivals.push(id),onInfo(){},isBlocked:()=>false,onNotice:message=>notices.push(message)});let now=window.performance.now();return {window,world,visited,arrivals,notices,tick(dt=16.667){now+=dt;frame(now);}};}
test('selecting a route never moves the character; keyboard movement follows it and arrival does not open chat',async()=>{
 for(const dt of [16.667,50]){const f=harness({x:15,z:7});f.world.guideTo('lab');for(let i=0;i<120;i++)f.tick(dt);assert.deepEqual({...f.world.getPosition()},{x:15,z:7});assert.equal(f.world.getNavigation().target,'lab');assert.ok(f.window.__scene.getObjectByName('navigation-route').children.length>0);
 f.window.dispatchEvent(new f.window.KeyboardEvent('keydown',{code:'KeyW'}));let frames=0;while(!f.arrivals.length&&frames++<400){f.tick(dt);const p=f.world.getPosition();assert.ok(canWalk(p.x,p.z));assert.ok(p.x>14.9);}
 f.window.dispatchEvent(new f.window.KeyboardEvent('keyup',{code:'KeyW'}));assert.deepEqual(f.arrivals,['lab']);assert.equal(f.world.getNavigation().target,null);await f.window.happyDOM.close();}
});
test('navigation focus freezes movement, offsets the camera to the left third, and resumes on close',async()=>{
 const f=harness({x:19.8,z:1});f.world.guideTo('lab');f.world.setNavigationOpen(true);f.window.dispatchEvent(new f.window.KeyboardEvent('keydown',{code:'KeyW'}));for(let i=0;i<60;i++)f.tick();assert.deepEqual({...f.world.getPosition()},{x:19.8,z:1});assert.ok(f.window.__camera.view?.enabled);assert.ok(f.window.__camera.position.toArray().every(Number.isFinite));f.world.setNavigationOpen(false);for(let i=0;i<90;i++)f.tick();assert.equal(f.window.__camera.view.enabled,false);let meshes=0;f.window.__scene.traverse(o=>{if(o.isMesh){meshes++;assert.ok(o.geometry.attributes.position.array.every(Number.isFinite));}});assert.ok(meshes>50);await f.window.happyDOM.close();
});

test('home suspends hidden world rendering and entering exploration resumes without teleporting',async()=>{const f=harness({x:15,z:7});f.tick();const count=f.window.__renderCount;f.world.setView('home');for(let i=0;i<30;i++)f.tick();assert.equal(f.window.__renderCount,count);assert.deepEqual({...f.world.getPosition()},{x:15,z:7});f.world.setView('third');f.tick();assert.ok(f.window.__renderCount>count);assert.deepEqual({...f.world.getPosition()},{x:15,z:7});await f.window.happyDOM.close();});

test('library inspection switches between exterior and interior without moving the student',async()=>{const f=harness({x:15,z:7});f.world.setView('library');for(const preset of ['hero','front','side','inside']){f.world.setInspectionPreset(preset);for(let i=0;i<30;i++)f.tick();assert.deepEqual({...f.world.getPosition()},{x:15,z:7});assert.ok(f.window.__camera.position.toArray().every(Number.isFinite));}f.world.setView('third');f.tick();assert.deepEqual({...f.world.getPosition()},{x:15,z:7});await f.window.happyDOM.close();});

test('all building cameras show their actual location without changing the student position',async()=>{const f=harness({x:0,z:16});f.world.setView('library');for(const building of ['office','lab','gate','library']){f.world.setInspectionBuilding(building);for(const preset of ['hero','front','side','inside']){f.world.setInspectionPreset(preset);for(let i=0;i<60;i++)f.tick();assert.deepEqual({...f.world.getPosition()},{x:0,z:16});assert.ok(f.window.__camera.position.toArray().every(Number.isFinite));}const expected=building==='office'?-15:building==='lab'?15:0;assert.ok(Math.abs(f.window.__camera.position.x-expected)<.01);}await f.window.happyDOM.close();});


test('manual movement collides with walls and route guidance survives keyboard input',async()=>{
 const f=harness({x:19.8,z:1});f.world.guideTo('lab');f.window.dispatchEvent(new f.window.KeyboardEvent('keydown',{code:'KeyA'}));for(let i=0;i<180;i++){f.tick();const p=f.world.getPosition();assert.ok(canWalk(p.x,p.z));}assert.equal(f.world.getNavigation().target,'lab');assert.equal(f.arrivals.length,0);f.world.setNavigationOpen(true);const before=f.world.getPosition();for(let i=0;i<30;i++)f.tick();assert.deepEqual({...f.world.getPosition()},{...before});await f.window.happyDOM.close();
});

test('pointer lock rotates without dragging and Control releases and recaptures the cursor',async()=>{
 const f=harness({x:0,z:16}),d=f.window.document,canvas=d.querySelector('canvas');
 canvas.requestPointerLock=()=>{Object.defineProperty(d,'pointerLockElement',{value:canvas,configurable:true});d.dispatchEvent(new f.window.Event('pointerlockchange'));return Promise.resolve();};
 d.exitPointerLock=()=>{Object.defineProperty(d,'pointerLockElement',{value:null,configurable:true});d.dispatchEvent(new f.window.Event('pointerlockchange'));};
 f.world.captureCursor();assert.equal(d.body.dataset.cursor,'scene');f.tick();const before=f.window.__camera.position.clone();canvas.dispatchEvent(new f.window.MouseEvent('pointermove',{movementX:150,movementY:10}));for(let i=0;i<30;i++)f.tick();assert.ok(before.distanceTo(f.window.__camera.position)>.1);
 f.window.dispatchEvent(new f.window.KeyboardEvent('keydown',{code:'ControlLeft'}));assert.equal(d.body.dataset.cursor,'ui');f.window.dispatchEvent(new f.window.KeyboardEvent('keydown',{code:'ControlLeft'}));assert.equal(d.body.dataset.cursor,'scene');f.world.setNavigationOpen(true);assert.equal(d.body.dataset.cursor,'ui');await f.window.happyDOM.close();
});


test('diagonal route dashes align with their path, rather than crossing it like tiles',async()=>{
 const f=harness({x:2,z:17});f.world.guideTo('gate');f.tick();
 const group=f.window.__scene.getObjectByName('navigation-route');group.updateMatrixWorld(true);
 const dashes=group.children.filter((_,i)=>i%2===1),points=[[2,17],...f.world.getNavigation().points];
 assert.ok(dashes.length>1);
 for(const dash of dashes){const a=dash.geometry.attributes.position;const p=dash.position.clone().fromBufferAttribute(a,0).applyMatrix4(dash.matrixWorld),q=dash.position.clone().fromBufferAttribute(a,2).applyMatrix4(dash.matrixWorld);const vx=q.x-p.x,vz=q.z-p.z;
  assert.ok(points.slice(1).some((end,i)=>{const start=points[i],dx=end[0]-start[0],dz=end[1]-start[1];return Math.abs(vx*dz-vz*dx)<1e-6;}),'each long edge must be parallel to a route segment');
  assert.ok(dash.geometry.parameters.width<dash.geometry.parameters.height);
 }
 await f.window.happyDOM.close();
});

test('wheel zoom responds clearly to a short scroll and normalizes line units',async()=>{
 async function zoom(deltaY,deltaMode){const f=harness({x:0,z:16});for(let i=0;i<100;i++)f.tick();const before=f.window.__camera.position.clone();f.window.document.querySelector('canvas').dispatchEvent(new f.window.WheelEvent('wheel',{deltaY,deltaMode}));for(let i=0;i<120;i++)f.tick();const after=f.window.__camera.position.clone();assert.ok(before.distanceTo(after)>1,'100 pixels should change the distance by over a metre');await f.window.happyDOM.close();return after;}
 const pixel=await zoom(-96,0),line=await zoom(-6,1);assert.ok(pixel.distanceTo(line)<1e-6);
});

test('returning from home renders a visible camera approach before declaring the scene ready',async()=>{
 const f=harness({x:0,z:16});f.tick();f.world.setView('home');f.world.setView('third');let ready=false;f.world.whenSceneReady().then(value=>ready=value);f.tick();const far=f.window.__camera.position.clone();await Promise.resolve();assert.equal(ready,false);for(let i=0;i<35;i++)f.tick();await Promise.resolve();assert.equal(ready,false);assert.ok(far.distanceTo(f.window.__camera.position)>1);for(let i=0;i<60;i++)f.tick();await Promise.resolve();assert.equal(ready,true);assert.deepEqual({...f.world.getPosition()},{x:0,z:16});await f.window.happyDOM.close();
});

test('leaving a pending scene restoration cancels its conversation handoff',async()=>{
 const f=harness({x:0,z:16});f.world.setView('home');f.world.setView('third');const ready=f.world.whenSceneReady();f.tick();f.world.setView('home');assert.equal(await ready,false);f.world.setView('third');const ready2=f.world.whenSceneReady();f.world.setNavigationOpen(true);assert.equal(await ready2,false);await f.window.happyDOM.close();
});
