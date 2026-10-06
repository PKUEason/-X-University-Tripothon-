import test from 'node:test';
import assert from 'node:assert/strict';
import {ConnectedSession,STORAGE_KEY,LEGACY_STORAGE_KEY,tasksIn} from '../src/service.js';
import {readSseStream} from '../src/sdk.js';
import {spaces,canWalk,routeTo} from '../src/campus.js';
const memory=()=>{const data=new Map();return {getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)};};
function fixture(){const storage=memory();let status='created',calls=0;const requests=[];const client={
 createSession:async()=>({session_id:'server-assigned'}),
 getQuest:async()=>({status,session_id:'server-assigned'}),getSession:async()=>({session:{goal:'goal'},roadmap:null,messages:[]}),
 advanceQuest:async(input,handlers)=>{calls++;requests.push(input);await new Promise(r=>setTimeout(r,5));status='quest_ready';return {status};}
 };const session=new ConnectedSession({storage,client,health:async()=>({mock_mode:false})});return {session,storage,requests,getCalls:()=>calls,client};}
test('real server ID is persisted; double submit sends one request',async()=>{const f=fixture();const first=f.session.clarify('goal');assert.equal(await f.session.clarify('duplicate'),false);await first;assert.equal(f.getCalls(),1);assert.equal(f.requests[0].session_id,'server-assigned');assert.equal(f.session.state.quest.status,'quest_ready');assert.equal(JSON.parse(f.storage.getItem(STORAGE_KEY)).projects[0].sessionId,'server-assigned');});
test('restore re-reads server stage rather than trusting local cached stage',async()=>{const f=fixture();await f.session.clarify('goal');const saved=JSON.parse(f.storage.getItem(STORAGE_KEY));saved.projects[0].quest.status='lab';f.storage.setItem(STORAGE_KEY,JSON.stringify(saved));const next=new ConnectedSession({storage:f.storage,client:f.client,health:async()=>({mock_mode:false})});await next.recover();assert.equal(next.state.quest.status,'quest_ready');assert.equal(f.getCalls(),1);});
test('failed request is visible and retry retains request ID',async()=>{const f=fixture();f.client.advanceQuest=async input=>{f.requests.push(input);throw Error('Disconnected');};await f.session.clarify('goal');assert.match(f.session.error,/Disconnected/);const id=f.requests[0].request_id;await f.session.clarify('goal');assert.equal(f.requests[1].request_id,id);assert.equal(f.session.state.quest.status,'created');});
test('fallback signal persists and partial live text is cleared',async()=>{const f=fixture();f.session.handlers().onToken('partial');f.session.handlers().onFallback('provider unavailable');assert.equal(f.session.stream,'');assert.deepEqual(f.session.state.fallbacks,['provider unavailable']);});
test('all space-to-space routes stay outside walls and pass through doors',()=>{for(const a of Object.values(spaces))for(const b of Object.keys(spaces)){let [x,z]=a.spawn;for(const [tx,tz] of routeTo({x,z},b)){const n=Math.ceil(Math.hypot(tx-x,tz-z)/.05)||1;for(let i=0;i<=n;i++)assert.ok(canWalk(x+(tx-x)*i/n,z+(tz-z)*i/n),`${a.name} -> ${b} at ${x+(tx-x)*i/n},${z+(tz-z)*i/n}`);[x,z]=[tx,tz];}}});
test('task context maps office to the backend professor_office ID',()=>{assert.equal(tasksIn({stages:[{id:'s3',space:'professor_office',tasks:[{id:'t3'}]}]},'office')[0].stage_id,'s3');});
test('SDK consumes fragmented unicode, CRLF and post-done quest events',async()=>{const raw='event: token\r\ndata: {"type":"token","delta":"学习"}\r\n\r\nevent: done\r\ndata: {"type":"done"}\r\n\r\nevent: quest\r\ndata: {"type":"quest","status":"library"}\r\n\r\n';const bytes=new TextEncoder().encode(raw),out=[];const stream=new ReadableStream({start(c){for(let i=0;i<bytes.length;i+=3)c.enqueue(bytes.slice(i,i+3));c.close();}});await readSseStream(new Response(stream),(event,data)=>out.push([event,data]));assert.equal(out[0][1].delta,'学习');assert.equal(out.at(-1)[1].status,'library');});
test('SDK surfaces malformed streams and callback errors',async()=>{await assert.rejects(readSseStream(new Response('event: token\ndata: broken\n\n'),()=>{}),/无效数据/);await assert.rejects(readSseStream(new Response('event: token\ndata: {"delta":"ok"}\n\n'),()=>{throw Error('handler failed');}),/handler failed/);});
test('SDK cancellation never resolves as a successful reply',async()=>{const ctrl=new AbortController();const stream=new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('event: token\ndata: {"delta":"partial"}\n\n'));}});const p=readSseStream(new Response(stream),()=>ctrl.abort(),ctrl.signal);await assert.rejects(p,e=>e.name==='AbortError');});

test('empty professor result cannot complete discussion',async()=>{const f=fixture();f.session.state.sessionId='server-assigned';f.client.getQuest=async()=>({status:'professor',professor_result:{answer:'  '}});assert.equal(await f.session.finishDiscussion(),false);assert.match(f.session.error,/先获得教授回复/);assert.equal(f.getCalls(),0);});
test('empty professor stream displays an error',async()=>{const f=fixture();f.session.state.sessionId='server-assigned';f.client.getSession=async()=>({session:{goal:'goal'},roadmap:{stages:[]},messages:[]});f.client.streamProfessorChat=async()=>({text:'  '});assert.equal(await f.session.discuss('下一步'),false);assert.match(f.session.error,/没有返回回答正文/);});

test('legacy session migrates once without losing conversation or stage',()=>{
 const storage=memory();storage.setItem(LEGACY_STORAGE_KEY,JSON.stringify({sessionId:'legacy-7',goal:'校园机器人',quest:{status:'lab'},messages:[{content:'定义两米误差'}],position:{x:15,z:1},spaceId:'lab'}));
 const s=new ConnectedSession({storage});assert.equal(s.projects.length,1);assert.equal(s.state.sessionId,'legacy-7');assert.equal(s.state.quest.status,'lab');s.persist();
 const restored=new ConnectedSession({storage});assert.equal(restored.state.projectId,s.state.projectId);assert.equal(restored.state.messages[0].content,'定义两米误差');
});
test('switching projects isolates artifacts, drafts and stage; profile survives reload',()=>{
 const storage=memory(),s=new ConnectedSession({storage});s.setProfile({nickname:' 小禾 ',gender:'female'});const first=s.state.projectId;
 s.state.goal='机器人';s.state.sessionId='A';s.state.quest={status:'lab',professor_result:{answer:'两米误差'}};s.state.draftMessage='还没发送的问题';
 s.newProject('文生图');const second=s.state.projectId;assert.equal(s.state.sessionId,null);assert.equal(s.state.quest.status,'created');assert.deepEqual(s.state.messages,[]);
 s.state.sessionId='B';s.state.quest={status:'library',library_result:{documents:[{title:'B资料'}]}};s.persist();
 s.switchProject(first);assert.equal(s.state.sessionId,'A');assert.equal(s.state.quest.status,'lab');assert.equal(s.state.draftMessage,'还没发送的问题');assert.equal(s.state.quest.library_result,undefined);
 const restored=new ConnectedSession({storage});assert.deepEqual(restored.profile,{nickname:'小禾',gender:'female',role:'learner'});assert.equal(restored.state.projectId,first);assert.equal(restored.projects.length,2);restored.switchProject(second);assert.equal(restored.state.sessionId,'B');assert.equal(restored.state.quest.professor_result,undefined);
});
test('profile is validated and nickname goes to new backend sessions',async()=>{
 const f=fixture();assert.throws(()=>f.session.setProfile({nickname:'  ',gender:'male'}));assert.throws(()=>f.session.setProfile({nickname:'小林',gender:'invalid'}));
 f.session.setProfile({nickname:'小林',gender:'male'});let input;f.client.createSession=async body=>{input=body;return {session_id:'new-id'};};await f.session.clarify('目标');assert.equal(input.nickname,'小林');
});
test('inflight response cannot leak into another project',async()=>{
 const f=fixture();const first=f.session.state.projectId;f.session.newProject('第二个');const second=f.session.state.projectId;f.session.switchProject(first);
 let release;f.client.advanceQuest=()=>new Promise(resolve=>{release=resolve;});const pending=f.session.clarify('目标');while(!release)await new Promise(r=>setTimeout(r,1));
 assert.equal(f.session.switchProject(second),false);assert.equal(f.session.newProject('第三个'),false);release({});await pending;assert.equal(f.session.state.projectId,first);f.session.switchProject(second);assert.equal(f.session.state.sessionId,null);
});
test('project selection re-reads its own server state',async()=>{
 const f=fixture();f.session.state.sessionId='A';const a=f.session.state.projectId;f.session.newProject('B');f.session.state.sessionId='B';f.session.persist();
 const requested=[];f.client.getSession=async id=>{requested.push(id);return {session:{goal:id},messages:[{content:id}],roadmap:null};};f.client.getQuest=async id=>({status:id==='A'?'professor':'library'});
 f.session.switchProject(a);await f.session.recover();assert.deepEqual(requested,['A']);assert.equal(f.session.state.quest.status,'professor');assert.equal(f.session.state.messages[0].content,'A');
});

test('quest-ready accepts another Scholar reply instead of generating a roadmap',async()=>{const f=fixture();await f.session.clarify('goal');await f.session.clarify('做仿真，周期一个月');assert.equal(f.requests.length,2);assert.equal(f.requests[1].expected_status,'quest_ready');assert.equal(f.requests[1].message,'做仿真，周期一个月');});
test('old Library cache refreshes against active session without quest advancement',async()=>{const f=fixture();f.session.state.sessionId='robot-project';let refreshed=false;f.client.getSession=async()=>({session:{goal:'柔性机器人'},roadmap:{stages:[]},messages:[]});f.client.getQuest=async()=>({status:'professor',library_result:refreshed?{retrieval_version:3,documents:[{title:'SoftRobots'}]}:{documents:[{title:'DDPM'}]}});f.client.libraryRetrieve=async input=>{assert.deepEqual(input,{session_id:'robot-project',query:''});refreshed=true;};await f.session.visit('library');assert.equal(f.session.state.quest.status,'professor');assert.equal(f.session.state.quest.library_result.documents[0].title,'SoftRobots');assert.equal(f.getCalls(),0);});
test('Scholar follow-up after roadmap keeps existing project stage',async()=>{const f=fixture();f.session.state.sessionId='robot-project';f.client.getQuest=async()=>({status:'professor'});let prompt;f.client.streamClarify=async body=>{prompt=body;return {text:'可以先做仿真'};};assert.equal(await f.session.clarify('先做仿真可以吗'),true);assert.equal(prompt.session_id,'robot-project');assert.equal(f.session.state.quest.status,'professor');assert.equal(f.getCalls(),0);});

test('delete inactive project removes only its backend session and survives reload',async()=>{
 const f=fixture();f.session.state.sessionId='A';const a=f.session.state.projectId;f.session.state.draftGoal='keep draft';f.session.newProject('B');const b=f.session.state.projectId;f.session.state.sessionId='B';f.session.switchProject(a);const deleted=[];f.client.deleteSession=async id=>deleted.push(id);f.storage.setItem(LEGACY_STORAGE_KEY,JSON.stringify({sessionId:'B',quest:{status:'lab'}}));
 assert.equal(await f.session.deleteProject(b),true);assert.deepEqual(deleted,['B']);assert.equal(f.storage.getItem(LEGACY_STORAGE_KEY),'null');assert.equal(f.session.state.projectId,a);assert.equal(f.session.state.draftGoal,'keep draft');const restored=new ConnectedSession({storage:f.storage});assert.deepEqual(restored.projects.map(p=>p.sessionId),['A']);
});
test('delete active project selects remaining project without mixing saved progress',async()=>{
 const f=fixture();const a=f.session.state.projectId;f.session.state.quest={status:'lab'};f.session.state.draftMessage='A draft';f.session.newProject('B');const b=f.session.state.projectId;f.session.state.sessionId='B';f.client.deleteSession=async()=>({ok:true});assert.equal(await f.session.deleteProject(b),true);assert.equal(f.session.state.projectId,a);assert.equal(f.session.state.quest.status,'lab');assert.equal(f.session.state.draftMessage,'A draft');
});
test('delete final unsent project works offline and empty workspace survives legacy migration',async()=>{
 const f=fixture();f.storage.setItem(LEGACY_STORAGE_KEY,JSON.stringify({sessionId:'old',quest:{status:'lab'}}));f.session.setProfile({nickname:'小禾',gender:'female'});f.session.health=async()=>{throw Error('offline');};assert.equal(await f.session.deleteProject(f.session.state.projectId),true);assert.equal(f.session.projects.length,0);f.session.persist();const restored=new ConnectedSession({storage:f.storage});assert.equal(restored.projects.length,0);assert.equal(restored.profile.nickname,'小禾');restored.newProject('再次开始');assert.equal(restored.projects.length,1);assert.equal(restored.state.sessionId,null);
});
test('failed or concurrent deletion preserves project and prevents switching',async()=>{
 const f=fixture();const a=f.session.state.projectId;f.session.state.sessionId='A';f.session.newProject('B');const b=f.session.state.projectId;let reject;f.client.deleteSession=()=>new Promise((_,r)=>{reject=r;});const pending=f.session.deleteProject(a);assert.equal(f.session.switchProject(a),false);assert.equal(f.session.newProject('C'),false);assert.equal(await f.session.deleteProject(b),false);reject(Error('offline'));assert.equal(await pending,false);assert.equal(f.session.projects.length,2);assert.equal(f.session.state.projectId,b);assert.match(f.session.error,/删除失败/);
});


test('campus identity migrates old profiles and survives switching, editing and reload',()=>{
 const storage=memory(),s=new ConnectedSession({storage});s.setProfile({nickname:'小禾',gender:'female'});
 const old=JSON.parse(storage.getItem(STORAGE_KEY));delete old.profile.role;storage.setItem(STORAGE_KEY,JSON.stringify(old));
 const migrated=new ConnectedSession({storage});assert.equal(migrated.profile.role,'learner');const original=migrated.state.projectId;
 for(const role of ['learner','tutor','builder']){
  migrated.setProfile({nickname:'小禾',gender:'female',role});migrated.newProject(role);migrated.switchProject(original);
  const reloaded=new ConnectedSession({storage});assert.equal(reloaded.profile.role,role);assert.equal(reloaded.profile.gender,'female');
  reloaded.setProfile({nickname:'新昵称',gender:'male'});assert.equal(reloaded.profile.role,role);
 }
 assert.throws(()=>migrated.setProfile({nickname:'小禾',gender:'female',role:'admin'}),/请选择/);
});

test('missing server session preserves the local snapshot and explicitly restores without AI generation',async()=>{
 const f=fixture();f.session.state.sessionId='lost';f.session.state.goal='保留目标';f.session.state.quest={status:'professor',library_result:{retrieval_version:4,results:[]}};f.session.state.roadmap={stages:[{tasks:[{id:'a',status:'done'}]}]};f.session.state.messages=[{role:'user',agent:'scholar',content:'保留对话'}];
 const snapshot=structuredClone(f.session.state);let restored;
 f.client.getSession=async id=>{if(id==='lost')throw Object.assign(Error('missing'),{status:404});return {session:{goal:'保留目标'},roadmap:snapshot.roadmap,messages:snapshot.messages};};
 f.client.restoreSession=async body=>{restored=body;return {session_id:'restored'};};f.client.getQuest=async()=>snapshot.quest;
 assert.equal(await f.session.recover(),false);assert.match(f.session.error,/本地备份/);assert.deepEqual(f.session.state.roadmap,snapshot.roadmap);assert.equal(await f.session.restoreMissingSession(),true);assert.equal(f.session.state.sessionId,'restored');assert.equal(restored.roadmap.stages[0].tasks[0].status,'done');assert.equal(restored.messages[0].content,'保留对话');assert.equal(f.getCalls(),0);
});

test('network outage never triggers snapshot restoration or loses cached progress',async()=>{
 const f=fixture();f.session.state.sessionId='offline';f.session.state.sessionMissing=true;f.session.state.quest={status:'lab'};let restores=0;f.client.getSession=async()=>{throw Error('network offline');};f.client.restoreSession=async()=>{restores++;};assert.equal(await f.session.restoreMissingSession(),false);assert.equal(restores,0);assert.equal(f.session.state.quest.status,'lab');assert.equal(f.session.state.sessionId,'offline');
});
