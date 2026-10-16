import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import {createHash} from 'node:crypto';
const root=new URL('../',import.meta.url).pathname;
const result=await build({stdin:{contents:`export * from './src/character-asset.js';export {createStudent} from './src/student.js';export {GLTFLoader} from './public/vendor/GLTFLoader.js';export * from './public/vendor/three.module.js';`,resolveDir:root},bundle:true,write:false,format:'esm',plugins:[{name:'local-three',setup(b){b.onResolve({filter:/^three$/},()=>({path:root+'public/vendor/three.module.js'}));b.onResolve({filter:/^\.\.\/vendor\//},a=>({path:root+'public/vendor/'+a.path.split('/').at(-1)}));}}]});
const {instantiateCharacter,createStudent,GLTFLoader,Texture,Vector3,AnimationMixer,Box3}=await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
const assets={};
for(const gender of ['male','female']){
 const bytes=await readFile(root+`public/assets/${gender==='male'?'student-male-zip':'student-female'}.glb`);
 const loader=new GLTFLoader();loader.register(()=>({name:'cpu-textures',loadTexture:()=>Promise.resolve(new Texture())}));
 assets[gender]=await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
}
for(const [gender,asset] of Object.entries(assets)){
 test(`${gender}: supplied skin, embedded textures and all original actions survive conversion`,()=>{
  assert.deepEqual(new Set(asset.animations.map(a=>a.name)),new Set(['Idle','Walk','Run','Greet','Clap',...(gender==='male'?['Dance']:[])]));
  assert.equal(asset.parser.json.skins[0].joints.length,65);
  assert.ok(asset.parser.json.images.every(i=>i.bufferView!==undefined));
  assert.ok(asset.scene.userData.locomotionSpeed.Walk>0);
  const c=instantiateCharacter(asset,'learner');c.update(.02,false,false);c.root.updateMatrixWorld(true);
  const bounds=new Box3().setFromObject(c.root,true),size=bounds.getSize(new Vector3());
  assert.ok(size.y>1.7&&size.y<1.85,`normalized height ${size.y}`);
  assert.ok(Math.abs(bounds.min.y)<.015,`idle floor ${bounds.min.y}`);
  c.root.traverse(o=>{if(!o.isSkinnedMesh)return;const w=o.geometry.attributes.skinWeight;for(let i=0;i<w.count;i++)assert.ok(Math.abs(w.getX(i)+w.getY(i)+w.getZ(i)+w.getW(i)-1)<1e-4);});c.dispose();
 });
 test(`${gender}: locomotion loops in place and every action deforms finite geometry`,()=>{
  const c=instantiateCharacter(asset,'learner');
  for(const clip of asset.animations){
   const m=new AnimationMixer(c.root);m.clipAction(clip).play();const hips=[];
   for(let i=0;i<=40;i++){
    m.setTime(clip.duration*i/40);c.root.updateMatrixWorld(true);
    const hip=c.root.getObjectByName('mixamorigHips').getWorldPosition(new Vector3());hips.push(hip);
    c.root.traverse(o=>{if(!o.isSkinnedMesh)return;o.skeleton.update();for(let v=0;v<o.geometry.attributes.position.count;v+=101){const p=o.getVertexPosition(v,new Vector3()).applyMatrix4(o.matrixWorld);assert.ok(p.toArray().every(Number.isFinite));assert.ok(p.length()<4,`${clip.name} escaped campus origin`);}});
   }
   if(['Walk','Run'].includes(clip.name)){assert.ok(hips.every(h=>Math.hypot(h.x-hips[0].x,h.z-hips[0].z)<.12),'root drifts away from actor');assert.ok(hips[0].distanceTo(hips.at(-1))<.001,'loop seam');}
   m.stopAllAction();m.uncacheRoot(c.root);
  }c.dispose();
 });
 test(`${gender}: rigs animate independently and gestures finish or yield to locomotion`,()=>{
  const a=instantiateCharacter(asset,'tutor'),b=instantiateCharacter(asset,'builder');const bone=c=>c.root.getObjectByName('mixamorigLeftUpLeg');const initial=bone(b).quaternion.clone();
  for(let i=0;i<30;i++)a.update(.02,true,false,false,1.2);
  assert.equal(a.root.userData.motion,'Walk');assert.ok(bone(b).quaternion.equals(initial));assert.ok(!bone(a).quaternion.equals(initial));
  assert.equal(a.playMotion('Greet'),true);a.update(.02,false,false);assert.equal(a.root.userData.motion,'Greet');
  for(let i=0;i<300;i++)a.update(.05,false,false);assert.equal(a.root.userData.motion,'Idle');
  a.playMotion('Clap');a.update(.02,true,true,false,1.98);assert.equal(a.root.userData.motion,'Run');assert.equal(a.playMotion('Dance'),gender==='male');assert.equal(a.playMotion('unknown'),false);
  a.dispose();b.update(.02,true,false);b.dispose();
 });
}
test('gender routes the loader; fallback replacement, disposal and errors are safe',async()=>{
 const genders=[];const c=createStudent({gender:'female'},{loadAsset:async gender=>{genders.push(gender);return assets[gender];}});
 assert.equal(await c.ready,true);assert.deepEqual(genders,['female']);assert.equal(c.root.userData.assetStatus,'ready');assert.ok(!c.root.getObjectByName('knit-sweater'));assert.ok(!c.availableMotions.includes('Dance'));c.dispose();
 let resolve;const late=createStudent({}, {loadAsset:()=>new Promise(r=>resolve=r)});await Promise.resolve();late.dispose();resolve(assets.male);assert.equal(await late.ready,false);assert.equal(late.root.children.length,0);
 const failed=createStudent({}, {loadAsset:async()=>{throw Error('offline');}});assert.equal(await failed.ready,false);assert.equal(failed.root.userData.assetStatus,'fallback');failed.dispose();
});
test('cadence follows distance and reduced motion settles into a stable idle',()=>{
 const a=instantiateCharacter(assets.male),b=instantiateCharacter(assets.male),thigh=c=>c.root.getObjectByName('mixamorigLeftUpLeg');
 for(let i=0;i<40;i++)a.update(.01,true,false,false,1.2);for(let i=0;i<80;i++)b.update(.01,true,false,false,.6);
 assert.ok(thigh(a).quaternion.clone().normalize().angleTo(thigh(b).quaternion.clone().normalize())<1e-5);
 for(let i=0;i<30;i++)a.update(.01,false,false,true,0);const idle=thigh(a).quaternion.clone();for(let i=0;i<30;i++)a.update(.01,false,false,true,0);
 assert.ok(idle.normalize().angleTo(thigh(a).quaternion.clone().normalize())<1e-5);a.dispose();b.dispose();
});

// Both characters must use the supplied lit surfaces, including normal and
// reflection maps; preview instances must not mutate cached campus materials.
test('both genders retain lit materials and texture channels without mutating shared sources',()=>{
 for(const gender of ['male','female']){
  const asset=assets[gender],source=[];asset.scene.traverse(o=>{if(o.isMesh)source.push(o.material);});
  const c=instantiateCharacter(asset,'learner');let count=0;
  c.root.traverse(o=>{if(!o.isMesh)return;count++;const original=source.find(m=>m.name===o.material.name);assert.ok(original);assert.notEqual(o.material,original);
   assert.equal(o.material.isMeshStandardMaterial,true);assert.equal(o.material.toneMapped,true);
   for(const channel of ['map','normalMap','metalnessMap','roughnessMap'])assert.equal(o.material[channel],original[channel]);
   assert.ok(o.material.color.equals(original.color));assert.equal(o.material.emissiveIntensity,original.emissiveIntensity);
   assert.equal(o.material.emissive.getHex(),0,'color correction must not glow in the dark');
   if(gender==='male'){
    assert.equal(o.material.isMeshPhysicalMaterial,true);
    assert.ok(o.material.metalness>0&&o.material.metalness<original.metalness);
    assert.ok(o.material.envMapIntensity>0&&o.material.envMapIntensity<original.envMapIntensity);
    assert.ok(o.material.specularIntensity>0&&o.material.specularIntensity<1);
    const shader={fragmentShader:'#include <color_fragment>\n#include <lights_physical_fragment>\n#include <tonemapping_fragment>'};o.material.onBeforeCompile(shader);
    assert.ok(shader.fragmentShader.includes('sRGBTransferEOTF'));
    assert.ok(shader.fragmentShader.includes('#include <lights_physical_fragment>'));
    assert.ok(shader.fragmentShader.includes('#include <tonemapping_fragment>'));
   }else{
    assert.equal(o.material.metalness,original.metalness);assert.equal(o.material.envMapIntensity,original.envMapIntensity);
    assert.equal(o.material.isMeshPhysicalMaterial,original.isMeshPhysicalMaterial);
    assert.equal(o.material.onBeforeCompile,original.onBeforeCompile);
   }
   o.material.color.set('#ff0000');assert.ok(!o.material.color.equals(original.color));
  });assert.ok(count>0);c.dispose();
 }
});

test('fresh male import embeds original ZIP color and normal bytes and has source provenance',async()=>{
 const report=JSON.parse(await readFile(root+'art/character/male-fresh-import-report.json','utf8'))[0];
 const bytes=await readFile(root+'public/assets/'+report.output),jsonLength=bytes.readUInt32LE(12),gltf=JSON.parse(bytes.subarray(20,20+jsonLength));
 assert.equal(createHash('sha256').update(bytes).digest('hex'),report.output_sha256);
 assert.equal(assets.male.scene.userData.sourceFBXSHA256,report.source_sha256);
 assert.equal(assets.male.scene.userData.sourceImport,'fresh-zip-native-textures');
 for(const expected of report.embedded_images.filter(image=>image.exact_zip_file)){
  const image=gltf.images.find(image=>image.name===expected.image),view=gltf.bufferViews[image.bufferView],offset=28+jsonLength+(view.byteOffset||0);
  assert.equal(createHash('sha256').update(bytes.subarray(offset,offset+view.byteLength)).digest('hex'),expected.sha256);
 }
 assert.equal(report.embedded_images.filter(image=>image.exact_zip_file).length,2);
});
