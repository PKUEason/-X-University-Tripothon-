import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {build} from 'esbuild';
const root=new URL('../',import.meta.url).pathname;
const built=await build({stdin:{contents:`export * from './src/building-assets.js';export {GLTFLoader} from './public/vendor/GLTFLoader.js';export * from './public/vendor/three.module.js';`,resolveDir:root},bundle:true,write:false,format:'esm',plugins:[{name:'local-three',setup(b){b.onResolve({filter:/^three$/},()=>({path:root+'public/vendor/three.module.js'}));b.onResolve({filter:/^\.\.\/vendor\//},a=>({path:root+'public/vendor/'+a.path.split('/').at(-1)}));}}]});
const {installBuildings,authoredBuildings,GLTFLoader,Scene,Group,Box3,Vector3,Raycaster}=await import('data:text/javascript;base64,'+Buffer.from(built.outputFiles[0].text).toString('base64'));
async function load(spec){const bytes=await readFile(root+'public/assets/'+spec.asset);return new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');}
test('all exported buildings have finite bounded geometry, contact shading and open ground-floor access',async()=>{
 for(const spec of authoredBuildings){
  const {scene}=await load(spec);scene.updateMatrixWorld(true);const size=new Box3().setFromObject(scene).getSize(new Vector3());
  assert.ok(size.x<13&&size.y<20&&size.z<12);let meshes=0,ao=0;
  scene.traverse(o=>{if(!o.isMesh)return;meshes++;assert.ok(o.geometry.attributes.position.array.every(Number.isFinite));if(o.geometry.attributes.color)ao++;});
  assert.ok(meshes<=16);assert.ok(ao>=5);
  // Keep head/shoulder clearance along every entrance and the existing interaction point.
  for(const x of [-.8,0,.8])for(const y of [.65,1.7]){
   const ray=new Raycaster(new Vector3(x,y,spec.space==='gate'?3:7),new Vector3(0,0,-1),0,spec.space==='gate'?6:6);
   assert.equal(ray.intersectObject(scene,true).length,0,`${spec.space} blocked entry ${x}/${y}`);
  }
 }
});
test('building failure is isolated; only successfully loaded shells are replaced',async()=>{
 const scene=new Scene(),slots=new Map(authoredBuildings.map(s=>[s.id,new Group()])),previous=new Map(slots),states=[];
 const models=await installBuildings(scene,slots,(s,id)=>states.push([s,id]),{async loadAsync(url){const spec=authoredBuildings.find(s=>url.endsWith(s.asset));if(spec.space==='lab')throw Error('network');return load(spec);}});
 assert.equal(models.filter(Boolean).length,2);assert.equal(slots.get('lab-shell'),previous.get('lab-shell'));assert.equal(previous.get('lab-shell').visible,true);
 for(const spec of authoredBuildings.filter(s=>s.space!=='lab')){assert.equal(previous.get(spec.id).visible,false);assert.deepEqual(slots.get(spec.id).position.toArray(),spec.position);}
 assert.ok(states.some(([s,id])=>s==='error'&&id==='lab'));
});
