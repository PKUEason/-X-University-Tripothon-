import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {build} from 'esbuild';
const root=new URL('../',import.meta.url).pathname;
const result=await build({stdin:{contents:`export * from './src/character-asset.js';export {createStudent} from './src/student.js';export {GLTFLoader} from './public/vendor/GLTFLoader.js';export * from './public/vendor/three.module.js';`,resolveDir:root},bundle:true,write:false,format:'esm',plugins:[{name:'local-three',setup(b){b.onResolve({filter:/^three$/},()=>({path:root+'public/vendor/three.module.js'}));b.onResolve({filter:/^\.\.\/vendor\//},a=>({path:root+'public/vendor/'+a.path.split('/').at(-1)}));}}]});
const {instantiateCharacter,createStudent,GLTFLoader,Texture,Vector3,AnimationMixer}=await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
const bytes=await readFile(root+'public/assets/student-rigged.glb');
const json=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());
const loader=new GLTFLoader();
// CPU inspection uses the actual skin/animation data; texture pixels are verified in browser.
loader.register(parser=>({name:'cpu-textures',loadTexture:()=>Promise.resolve(new Texture())}));
const asset=await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
test('export contains usable skin, normalized weights and three cyclic in-place animations',()=>{
 assert.deepEqual(new Set(asset.animations.map(a=>a.name)),new Set(['Idle','Walk','Run']));
 assert.equal(json.skins[0].joints.length,17);assert.ok(json.images.every(i=>i.bufferView!==undefined),'textures embedded');
 asset.scene.traverse(o=>{if(!o.isSkinnedMesh)return;const w=o.geometry.attributes.skinWeight;for(let i=0;i<w.count;i++)assert.ok(Math.abs(w.getX(i)+w.getY(i)+w.getZ(i)+w.getW(i)-1)<1e-4);});
 for(const clip of asset.animations){assert.ok(clip.duration>.5);for(const track of clip.tracks){const n=track.getValueSize();for(let i=0;i<n;i++)assert.ok(Math.abs(track.values[i]-track.values[track.values.length-n+i])<.002,`${clip.name} loops`);}}
});
test('live and preview rigs are independent, transition to walking/running/idle, and retain role colors',()=>{
 const a=instantiateCharacter(asset,'tutor'),b=instantiateCharacter(asset,'builder');
 const aBone=a.root.getObjectByName('ThighL')||a.root.getObjectByName('Thigh.L');
 const bBone=b.root.getObjectByName('ThighL')||b.root.getObjectByName('Thigh.L');
 assert.ok(aBone&&bBone);assert.notEqual(aBone,bBone);
 const initial=bBone.quaternion.clone();
 for(let i=0;i<20;i++)a.update(.016,true,false);
 assert.equal(a.root.userData.motion,'Walk');assert.ok(bBone.quaternion.equals(initial));assert.ok(!aBone.quaternion.equals(initial));
 a.update(.016,true,true);assert.equal(a.root.userData.motion,'Run');a.update(.016,false,false);assert.equal(a.root.userData.motion,'Idle');
 const found=[];a.root.traverse(o=>{if(o.isMesh&&o.material.name==='IdentityAccent')found.push(o.material.color.getHexString());});assert.ok(found.length>0);assert.ok(found.every(c=>c==='e99560'));
 // Deforming vertices stays finite across a complete run cycle.
 for(let t=0;t<80;t++){a.update(.016,true,true);a.root.updateMatrixWorld(true);a.root.traverse(o=>{if(o.isSkinnedMesh){o.skeleton.update();for(let i=0;i<o.geometry.attributes.position.count;i+=47){const p=o.getVertexPosition(i,new Vector3());assert.ok(p.toArray().every(Number.isFinite));assert.ok(p.length()<3);}}});}
 a.dispose();b.update(.02,true,false);assert.equal(b.root.userData.motion,'Walk');b.dispose();
});
test('loading replaces fallback atomically; disposal during loading and load failure are safe',async()=>{
 const character=createStudent({role:'learner'},{loadAsset:async()=>asset});assert.ok(character.root.getObjectByName('knit-sweater'));
 assert.equal(await character.ready,true);assert.equal(character.root.userData.assetStatus,'ready');assert.ok(!character.root.getObjectByName('knit-sweater'));character.dispose();
 let resolve;const late=createStudent({}, {loadAsset:()=>new Promise(r=>resolve=r)});await Promise.resolve();late.dispose();resolve(asset);assert.equal(await late.ready,false);assert.equal(late.root.children.length,0);
 const failure=createStudent({}, {loadAsset:async()=>{throw Error('offline');}});assert.equal(await failure.ready,false);assert.equal(failure.root.userData.assetStatus,'fallback');assert.ok(failure.root.getObjectByName('knit-sweater'));failure.dispose();
});

test('gait cadence follows travelled distance and reduced motion still settles into idle',()=>{
 const a=instantiateCharacter(asset,'learner'),b=instantiateCharacter(asset,'learner');
 const thigh=c=>c.root.getObjectByName('ThighL')||c.root.getObjectByName('Thigh.L');
 // Equal distance at half speed takes twice the time but reaches the same gait phase.
 for(let i=0;i<40;i++)a.update(.01,true,false,false,1.2);
 for(let i=0;i<80;i++)b.update(.01,true,false,false,.6);
 assert.ok(thigh(a).quaternion.clone().normalize().angleTo(thigh(b).quaternion.clone().normalize())<1e-5);
 const walking=thigh(a).quaternion.clone();
 for(let i=0;i<30;i++)a.update(.01,false,false,true,0);
 const idle=thigh(a).quaternion.clone();
 assert.ok(idle.angleTo(walking)>.01,'stopping must not freeze a walking pose');
 for(let i=0;i<30;i++)a.update(.01,false,false,true,0);
 assert.ok(idle.clone().normalize().angleTo(thigh(a).quaternion.clone().normalize())<1e-5,'idle stays still after crossfade');
 a.dispose();b.dispose();
});


test('walk extends the supporting knee, moves the upper body, and never skins one shoe triangle to both feet',()=>{
 const c=instantiateCharacter(asset,'learner'),mixer=new AnimationMixer(c.root);
 mixer.clipAction(asset.animations.find(a=>a.name==='Walk')).play();
 const bone=n=>c.root.getObjectByName(n.replace('.',''))||c.root.getObjectByName(n);
 const world=n=>bone(n).getWorldPosition(new Vector3());
 const duration=asset.animations.find(a=>a.name==='Walk').duration;
 for(const [side,phase] of [['L',.25],['R',.75]]){
  mixer.setTime(duration*phase);c.root.updateMatrixWorld(true);
  const hip=world('Thigh.'+side),knee=world('Shin.'+side),ankle=world('Foot.'+side);
  const angle=hip.sub(knee).angleTo(ankle.sub(knee))*180/Math.PI;
  assert.ok(angle>160,`supporting ${side} knee stays crouched: ${angle}`);
 }
 const heights=[],rotations=[];
 for(let i=0;i<20;i++){mixer.setTime(duration*i/20);c.root.updateMatrixWorld(true);heights.push(world('Head').y);rotations.push(bone('Head').quaternion.clone().normalize());}
 assert.ok(Math.max(...heights)-Math.min(...heights)>.018,'head follows the changing support height');
 assert.ok(rotations.some(q=>q.angleTo(rotations[0])>.01),'head is not rigidly locked');
 c.root.traverse(o=>{
  if(!o.isSkinnedMesh)return;
  const names=o.skeleton.bones.map(b=>b.name),j=o.geometry.attributes.skinIndex,w=o.geometry.attributes.skinWeight,ix=o.geometry.index;
  if(!ix)return;
  const foot=v=>{for(let k=0;k<4;k++){const n=names[j.getComponent(v,k)];if(w.getComponent(v,k)>.95&&/^Foot/.test(n))return n;}return null;};
  for(let i=0;i<ix.count;i+=3){const feet=new Set([0,1,2].map(k=>foot(ix.getX(i+k))).filter(Boolean));assert.ok(feet.size<=1,'a shoe face is pulled between opposite feet');}
 });
 mixer.stopAllAction();mixer.uncacheRoot(c.root);c.dispose();
});

test('walk support transfer and loop seam have no sharp hip-position impulse',()=>{
 const c=instantiateCharacter(asset,'learner'),mixer=new AnimationMixer(c.root),clip=asset.animations.find(a=>a.name==='Walk');
 mixer.clipAction(clip).play();const points=[],samples=160,dt=clip.duration/samples;
 for(let i=0;i<samples;i++){mixer.setTime(i*dt);c.root.updateMatrixWorld(true);points.push(c.root.getObjectByName('Hips').getWorldPosition(new Vector3()));}
 let peak=0;
 for(let i=0;i<samples;i++){const acceleration=points[(i+1)%samples].clone().add(points[(i+samples-1)%samples]).addScaledVector(points[i],-2).length()/(dt*dt);peak=Math.max(peak,acceleration);}
 // At this sampling interval the prior abrupt support switch measured 366.7.
 assert.ok(peak<150,`support transfer / seam impulse regressed: ${peak}`);
 mixer.stopAllAction();mixer.uncacheRoot(c.root);c.dispose();
});

function soleStats(c,side){
 const pts=[];
 c.root.updateMatrixWorld(true);
 c.root.traverse(o=>{if(!o.isSkinnedMesh)return;o.skeleton.update();const j=o.geometry.attributes.skinIndex,w=o.geometry.attributes.skinWeight;
 for(let i=0;i<j.count;i++)for(let k=0;k<4;k++)if(w.getComponent(i,k)>.95&&o.skeleton.bones[j.getComponent(i,k)].name.replace('.','')==='Foot'+side){pts.push(o.getVertexPosition(i,new Vector3()).applyMatrix4(o.matrixWorld));break;}
 });
 const zs=pts.map(p=>p.z),lo=Math.min(...zs),hi=Math.max(...zs),bins=[];
 for(let i=1;i<9;i++){const b=pts.filter(p=>p.z>=lo+(hi-lo)*i/10&&p.z<=lo+(hi-lo)*(i+1)/10);if(b.length)bins.push([b.reduce((v,p)=>v+p.z,0)/b.length,Math.min(...b.map(p=>p.y))]);}
 const slopes=[];for(let i=0;i<bins.length;i++)for(let j=i+1;j<bins.length;j++)if(bins[j][0]-bins[i][0]>.04)slopes.push((bins[j][1]-bins[i][1])/(bins[j][0]-bins[i][0]));slopes.sort((a,b)=>a-b);
 return {pitch:Math.atan(slopes[Math.floor(slopes.length/2)])*180/Math.PI,lowest:Math.min(...pts.map(p=>p.y)),bins};
}


test('both actual shoe soles lie level during support and idle, then roll off in their own turn',()=>{
 const c=instantiateCharacter(asset,'learner');
 for(const name of ['Idle','Walk']){
  const m=new AnimationMixer(c.root),clip=asset.animations.find(a=>a.name===name);m.clipAction(clip).play();
  for(const [side,offset] of [['L',0],['R',.5]]){
   for(const phase of name==='Idle'?[0,.25,.5]:[.18,.25,.30]){
    m.setTime(clip.duration*(name==='Idle'?phase:phase+offset));const sole=soleStats(c,side);
    assert.ok(Math.abs(sole.pitch)<3,`${name} ${side} support sole tilted ${sole.pitch} degrees`);
    assert.ok(Math.abs(sole.lowest)<.006,`${name} ${side} sole misses the ground: ${sole.lowest}`);
   }
   if(name==='Walk'){m.setTime(clip.duration*(.46+offset));assert.ok(soleStats(c,side).pitch>6,`${side} must roll off after supporting, not stay locked flat`);}
  }
  m.stopAllAction();m.uncacheRoot(c.root);
 }
 c.dispose();
});

// Sole pitch alone cannot detect a torn cuff: inspect lengths of the actual
// skinned surface edges on both feet, including partially weighted vertices.
test('shoe and ankle surfaces remain connected through complete idle, walk and run cycles',()=>{
 const c=instantiateCharacter(asset,'learner'),surfaces=[];
 c.root.traverse(o=>{
  if(!o.isSkinnedMesh||!o.geometry.index)return;
  const p=o.geometry.attributes.position,j=o.geometry.attributes.skinIndex,w=o.geometry.attributes.skinWeight,ix=o.geometry.index;
  const nearFoot=i=>[0,1,2,3].some(k=>w.getComponent(i,k)>.02&&/^Foot/.test(o.skeleton.bones[j.getComponent(i,k)].name));
  const edges=[];
  for(let t=0;t<ix.count;t+=3)for(let k=0;k<3;k++){
   const a=ix.getX(t+k),b=ix.getX(t+(k+1)%3);
   if(!nearFoot(a)&&!nearFoot(b))continue;
   const rest=new Vector3().fromBufferAttribute(p,a).distanceTo(new Vector3().fromBufferAttribute(p,b));
   if(rest>.003&&rest<.04)edges.push({a,b,rest});
  }
  if(edges.length)surfaces.push({o,edges,vertices:[...new Set(edges.flatMap(e=>[e.a,e.b]))]});
 });
 assert.ok(surfaces.length,'inspect the real shoe mesh');
 for(const clip of asset.animations){
  const m=new AnimationMixer(c.root);m.clipAction(clip).play();
  for(let frame=0;frame<80;frame++){
   m.setTime(clip.duration*frame/80);c.root.updateMatrixWorld(true);
   for(const {o,edges,vertices} of surfaces){
    o.skeleton.update();const points=new Map(vertices.map(i=>[i,o.getVertexPosition(i,new Vector3())]));
    for(const {a,b,rest} of edges){
     const ratio=points.get(a).distanceTo(points.get(b))/rest;
     assert.ok(ratio<2&&ratio>.18,`${clip.name} frame ${frame}: ankle edge tears or collapses (${ratio.toFixed(3)}x)`);
    }
   }
  }
  m.stopAllAction();m.uncacheRoot(c.root);
 }
 c.dispose();
});
