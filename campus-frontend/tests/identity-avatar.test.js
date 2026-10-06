import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {IDENTITIES} from '../src/identity.js';
const root=new URL('../',import.meta.url).pathname;
const bundle=await build({entryPoints:[root+'src/student.js'],bundle:true,write:false,format:'esm',alias:{three:root+'public/vendor/three.module.js'},plugins:[{name:'vendor',setup(b){b.onResolve({filter:/^\.\.\/vendor\//},a=>({path:root+'public/vendor/'+a.path.split('/').at(-1)}));}}]});
const {createProceduralStudent:createStudent}=await import('data:text/javascript;base64,'+Buffer.from(bundle.outputFiles[0].text).toString('base64'));
test('all three identities color both the live avatar and backpack independently of gender',()=>{
 for(const gender of ['male','female'])for(const [role,identity]of Object.entries(IDENTITIES)){
  const student=createStudent({gender,role});
  assert.equal(student.root.userData.identity,role);
  for(const name of ['knit-sweater','backpack-body'])assert.equal('#'+student.root.getObjectByName(name).material.color.getHexString(),identity.color);
  assert.equal(!!student.root.getObjectByName('sculpted-bob-back'),gender==='female');
  student.dispose();
 }
});
