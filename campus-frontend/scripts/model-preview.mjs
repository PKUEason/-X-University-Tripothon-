// Offline geometry inspection only; this does not render or automate a browser.
import {build} from 'esbuild';
import {writeFile,mkdir} from 'node:fs/promises';
import {pathToFileURL,fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
await mkdir(root+'evidence',{recursive:true});
const result=await build({stdin:{contents:`export {createStudent} from './src/student.js';`,resolveDir:root},bundle:true,format:'esm',platform:'node',write:false,alias:{three:root+'public/vendor/three.module.js'}});
await writeFile(root+'evidence/student-inspect.mjs',result.outputFiles[0].text);
const {createStudent}=await import(pathToFileURL(root+'evidence/student-inspect.mjs'));
for(const gender of ['male','female']){const student=createStudent({gender});student.root.updateMatrixWorld(true);const meshes=[];student.root.traverse(o=>{if(!o.isMesh)return;const g=o.geometry.clone().applyMatrix4(o.matrixWorld);meshes.push({name:o.name,color:'#'+o.material.color.getHexString(),position:Array.from(g.attributes.position.array),normal:Array.from(g.attributes.normal.array),index:g.index?Array.from(g.index.array):null});g.dispose();});await writeFile(root+`evidence/student-${gender}.json`,JSON.stringify(meshes));console.log(gender,meshes.length,'meshes');student.dispose();}
