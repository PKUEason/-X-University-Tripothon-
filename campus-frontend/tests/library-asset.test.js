import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {build} from 'esbuild';
const root=new URL('../',import.meta.url).pathname;
const result=await build({stdin:{contents:`export {installLibrary} from './src/library-asset.js';export {GLTFLoader} from './public/vendor/GLTFLoader.js';export * from './public/vendor/three.module.js';`,resolveDir:root},bundle:true,write:false,format:'esm',plugins:[{name:'local-three',setup(b){b.onResolve({filter:/^three$/},()=>({path:root+'public/vendor/three.module.js'}));b.onResolve({filter:/^\.\.\/vendor\//},a=>({path:root+'public/vendor/'+a.path.split('/').at(-1)}));}}]});
const {installLibrary,GLTFLoader,Scene,Group,Box3,Vector3,Raycaster}=await import('data:text/javascript;base64,'+Buffer.from(result.outputFiles[0].text).toString('base64'));
const bytes=await readFile(root+'public/assets/library-refined.glb');
const load=()=>new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
test('actual Blender GLB has bounded finite geometry, transparent glazing and a clear navigable entrance',async()=>{
 const {scene}=await load();scene.updateMatrixWorld(true);
 const bounds=new Box3().setFromObject(scene);const size=bounds.getSize(new Vector3());
 assert.ok(size.x>20&&size.x<22);assert.ok(size.y>26&&size.y<29);assert.ok(size.z>26&&size.z<29);
 let glass=0,ao=0,meshes=0;
 scene.traverse(o=>{if(!o.isMesh)return;meshes++;assert.ok(o.geometry.attributes.position.array.every(Number.isFinite));if(o.geometry.attributes.color)ao++;if(o.material.name.startsWith('Glazing')){glass++;assert.ok(o.material.transparent);assert.ok(o.material.opacity<.6);}});
 assert.ok(meshes<25);assert.ok(glass>=2);assert.ok(ao>5,'baked contact shading is present in the exported asset');
 // Eye and shoulder-height rays along the central entry must reach the reading hall.
 for(const x of [-2,0,2])for(const y of [.7,1.7]){
   const ray=new Raycaster(new Vector3(x,y,16),new Vector3(0,0,-1),0,10);
   assert.equal(ray.intersectObject(scene,true).length,0,`blocked entry at ${x},${y}`);
 }
});
test('asset loading atomically replaces the fallback, while failure keeps the existing building visible',async()=>{
 const scene=new Scene(),fallback=new Group(),slots=new Map([['library-shell',fallback]]),status=[];scene.add(fallback);
 const model=await installLibrary(scene,slots,s=>status.push(s),{loadAsync:load});
 assert.deepEqual(status,['loading','ready']);assert.equal(fallback.visible,false);assert.equal(slots.get('library-shell'),model);assert.deepEqual(model.position.toArray(),[0,0,-25]);
 const failedFallback=new Group(),failedSlots=new Map([['library-shell',failedFallback]]),failed=[];
 assert.equal(await installLibrary(scene,failedSlots,s=>failed.push(s),{loadAsync(){throw Error('offline')}}),null);
 assert.equal(failedFallback.visible,true);assert.equal(failedSlots.get('library-shell'),failedFallback);assert.deepEqual(failed,['loading','error']);
});
