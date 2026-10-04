import assert from 'node:assert/strict';
import {XUniversityClient} from '../src/sdk.js';
const base=process.env.XUNI_SMOKE_BASE??'http://127.0.0.1:8001';
const health=await fetch(base+'/health').then(r=>r.json());
assert.equal(health.mock_mode,true,'Repeated smoke test requires MOCK_MODE=true');
const client=new XUniversityClient(base+'/api');
const count=Number(process.env.XUNI_SMOKE_COUNT??10),results=[];
for(let i=0;i<count;i++){
 const {session_id}=await client.createSession({goal:'两周扩散模型实验'});
 const advance=async(message)=>{const q=await client.getQuest(session_id);const r=await client.advanceQuest({session_id,message,request_id:crypto.randomUUID(),expected_status:q.status});assert.equal(r.error,undefined);return r;};
 await advance('我想学习扩散模型');await advance('我有 PyTorch 基础，每天 3 小时');
 await advance();assert.equal((await client.getQuest(session_id)).status,'library');
 await advance();assert.equal((await client.getQuest(session_id)).status,'professor');
 const snap=await client.getSession(session_id);const stage=snap.roadmap.stages.find(s=>s.space==='professor_office');
 const professor=await client.streamProfessorChat({session_id,message:'比较 20 与 50 步采样的实验范围',task_id:stage?.tasks[0]?.id});assert.ok(professor.text);
 const request={session_id,request_id:crypto.randomUUID(),expected_status:'professor'};
 await client.advanceQuest(request);await client.advanceQuest(request);assert.equal((await client.getQuest(session_id)).status,'lab');
 await advance();const q=await client.getQuest(session_id);assert.equal(q.status,'project_ready');assert.ok(q.library_result.documents.length);assert.ok(q.professor_result.answer);assert.ok(q.lab_result.steps.length);assert.ok(q.project.degraded);assert.equal(q.completed_tasks.length,0);
 const task=snap.roadmap.stages.flatMap(s=>s.tasks)[0];await client.updateProgress(session_id,task.id,'done');assert.ok((await client.getQuest(session_id)).completed_tasks.includes(task.id));
 results.push({round:i+1,status:q.status,artifact:q.project.artifact_type,replaySafe:true,restored:true});
}
console.log(JSON.stringify({mode:'backend-mock',rounds:count,results},null,2));
