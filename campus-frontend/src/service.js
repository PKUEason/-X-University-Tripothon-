import {XUniversityClient} from './sdk.js';
export const LEGACY_STORAGE_KEY='xuni-connected-campus-v1';
export const STORAGE_KEY='xuni-campus-workspace-v2';
export const initial=()=>({projectId:crypto.randomUUID(),title:'我的第一个项目',draftGoal:'',draftScholarReply:'',draftMessage:'',sessionId:null,goal:'',spaceId:'gate',position:{x:0,z:16},quest:{status:'created'},roadmap:null,messages:[],fallbacks:[],request:null});
export function nextSpace(status){return ({created:'gate',clarifying:'gate',quest_ready:'gate',library:'library',professor:'office',lab:'lab',project_ready:'lab'})[status]??'gate';}
export function tasksIn(roadmap,space){const id=space==='office'?'professor_office':space;return (roadmap?.stages??[]).flatMap(s=>(s.tasks??[]).map(t=>({...t,stage_id:s.id,space:t.space??s.space}))).filter(t=>t.space===id);}
export class ConnectedSession{
 constructor({storage,client=new XUniversityClient('/api'),health=()=>fetch('/health').then(r=>{if(!r.ok)throw Error('后端未连接');return r.json();}),onChange=()=>{}}){
  this.storage=storage;this.client=client;this.health=health;this.onChange=onChange;this.busy=false;this.status='';this.error='';this.stream='';this.mode=null;
  this.profile=null;this.projects=[];
  try{
   const saved=JSON.parse(storage.getItem(STORAGE_KEY)||'null');
   if(saved?.version===2&&Array.isArray(saved.projects)){
    this.projects=saved.projects.filter(p=>p.projectId&&p.quest).map(p=>({...initial(),...p}));
    if(saved.profile?.nickname&&['male','female'].includes(saved.profile.gender))this.profile=saved.profile;
    this.state=this.projects.find(p=>p.projectId===saved.activeProjectId)??this.projects[0]??initial();
   }
   if(!this.state){const legacy=JSON.parse(storage.getItem(LEGACY_STORAGE_KEY)||'null');this.state=legacy?.sessionId&&legacy.quest?{...initial(),...legacy,title:legacy.goal?.slice(0,32)||'原有项目'}:initial();this.projects=[this.state];}
  }catch{this.state=initial();this.projects=[this.state];}
 }
 persist(){
  const index=this.projects.findIndex(p=>p.projectId===this.state.projectId);
  if(index>=0)this.projects[index]=this.state;
  try{this.storage.setItem(STORAGE_KEY,JSON.stringify({version:2,profile:this.profile,activeProjectId:this.state.projectId,projects:this.projects}));}catch{}
 }
 changed(){this.persist();this.onChange();}
 setProfile({nickname,gender}){nickname=nickname.trim();if(!nickname||nickname.length>24||!['male','female'].includes(gender))throw Error('请填写 1–24 字的昵称，并选择男生或女生。');this.profile={nickname,gender};this.changed();}
 newProject(title){if(this.busy)return false;this.persist();const {position,spaceId}=this.state;this.state={...initial(),title:title.trim()||'新项目',position:{...position},spaceId};this.projects.push(this.state);this.error='';this.stream='';this.changed();return true;}
 async deleteProject(id){
  if(this.busy)return false;
  const project=this.projects.find(p=>p.projectId===id);if(!project)return false;
  this.busy=true;this.error='';this.status='正在删除项目…';this.changed();
  try{
   if(project.sessionId)await this.client.deleteSession(project.sessionId);
   try{const legacy=JSON.parse(this.storage.getItem(LEGACY_STORAGE_KEY)||'null');if(project.sessionId&&legacy?.sessionId===project.sessionId)this.storage.setItem(LEGACY_STORAGE_KEY,'null');}catch{}
   const index=this.projects.indexOf(project),active=this.state.projectId===id;
   this.projects.splice(index,1);
   if(active){const {position,spaceId}=this.state;this.state=this.projects[Math.min(index,this.projects.length-1)]??initial();this.state.position={...position};this.state.spaceId=spaceId;this.stream='';}
   this.changed();return true;
  }catch(error){this.error='删除失败，项目仍保留。'+error.message;return false;}
  finally{this.busy=false;this.status='';this.changed();}
 }
 switchProject(id){if(this.busy)return false;const project=this.projects.find(p=>p.projectId===id);if(!project)return false;this.persist();const {position,spaceId}=this.state;this.state=project;this.state.position={...position};this.state.spaceId=spaceId;this.error='';this.stream='';this.changed();return true;}
 async sync(){if(!this.state.sessionId)return;const snapshot=await this.client.getSession(this.state.sessionId);const quest=await this.client.getQuest(this.state.sessionId);this.state.goal=snapshot.session.goal??this.state.goal;this.state.quest=quest;this.state.roadmap=snapshot.roadmap;this.state.messages=snapshot.messages??[];this.state.fallbacks=[...new Set([...this.state.fallbacks,...(quest.fallbacks??[]),...(quest.professor_result?.degraded?['Professor 回复曾降级为示例']:[])])];this.changed();}
 async run(fn){if(this.busy)return false;this.busy=true;this.error='';this.stream='';this.changed();try{this.mode=await this.health();await fn();return true;}catch(e){this.error=e.name==='TimeoutError'||e.name==='AbortError'?'请求已中断。请先恢复服务端进度，再决定是否重试。':e.message;try{await this.sync();}catch{}return false;}finally{this.busy=false;this.status='';this.changed();}}
 recover(){return this.run(async()=>{await this.sync();});}
 handlers(){return {
  onToken:delta=>{this.stream+=delta;this.changed();},
  onStatus:status=>{this.status=status;this.changed();},
  onQuest:(_status,message)=>{this.status=message;this.changed();},
  onFallback:reason=>{this.stream='';this.state.fallbacks=[...new Set([...this.state.fallbacks,reason])];this.changed();},
  onLabGuidance:g=>{if(g.degraded)this.state.fallbacks.push(g.degraded_reason??'Lab 示例方案');},
  onProject:p=>{if(p.degraded)this.state.fallbacks.push(p.degraded_reason??'成果卡示例');}
 };}
 async advance(message){
  const status=this.state.quest.status;
  const old=this.state.request;
  const request=old?.status==='pending'&&old.expected_status===status&&old.message===message?old:{session_id:this.state.sessionId,message,request_id:crypto.randomUUID(),expected_status:status,status:'pending'};
  this.state.request=request;this.changed();
  const {status:_local,...input}=request;
  const result=await this.client.advanceQuest(input,this.handlers(),AbortSignal.timeout(180000));
  if(result.error)throw Error(result.error);
  await this.sync();this.state.request=null;this.changed();
 }
 clarify(message){return this.run(async()=>{
  if(!this.projects.some(p=>p.projectId===this.state.projectId)){this.projects.push(this.state);this.changed();}
  if(!this.state.sessionId){const created=await this.client.createSession({goal:message,nickname:this.profile?.nickname});this.state.sessionId=created.session_id;this.state.goal=message;this.changed();}
  await this.sync();
  if(['created','clarifying','quest_ready'].includes(this.state.quest.status))await this.advance(message);
  else{const result=await this.client.streamClarify({session_id:this.state.sessionId,message},this.handlers(),AbortSignal.timeout(180000));if(result.error)throw Error(result.error);if(!result.text?.trim())throw Error('Scholar 没有返回回答正文，请重试。');await this.sync();}
 });}
 generateRoadmap(){return this.run(async()=>{await this.sync();if(this.state.quest.status!=='quest_ready')throw Error('请先补充目标、基础和时间，完成目标澄清。');await this.advance();});}
 visit(space){return this.run(async()=>{
  await this.sync();
  if(space==='library'&&this.state.quest.status==='library')await this.advance();
  else if(space==='library'&&this.state.roadmap&&this.state.quest.library_result?.retrieval_version!==3)await this.retrieveLibrary();
  if(space==='office'&&this.state.quest.status==='professor'&&!this.state.quest.professor_result?.answer?.trim())await this.professor('请结合我的目标和图书馆资料，帮我收敛一个可验证的项目问题，并提出一个我需要回答的关键问题。');
 });}
 async retrieveLibrary(){await this.client.libraryRetrieve({session_id:this.state.sessionId,query:''});await this.sync();}
 searchPapers(terms){return this.run(async()=>{await this.client.libraryRetrieve({session_id:this.state.sessionId,query:'',arxiv_query:terms});await this.sync();});}
 refreshLibrary(){return this.run(async()=>{await this.sync();if(this.state.quest.status==='library')await this.advance();else await this.retrieveLibrary();});}
 async professor(message){
  const task=tasksIn(this.state.roadmap,'office').find(t=>t.status!=='done')??tasksIn(this.state.roadmap,'office')[0];
  const result=await this.client.streamProfessorChat({session_id:this.state.sessionId,message,task_id:task?.id,stage_id:task?.stage_id},this.handlers(),AbortSignal.timeout(180000));
  if(result.error)throw Error(result.error);if(!result.text?.trim())throw Error('教授没有返回回答正文，请重试。');await this.sync();
 }
 discuss(message){return this.run(async()=>{await this.sync();if(!this.state.roadmap)throw Error('请先生成任务路线。');await this.professor(message);});}
 finishDiscussion(){return this.run(async()=>{await this.sync();if(this.state.quest.status!=='professor'||!this.state.quest.professor_result?.answer?.trim())throw Error('请先获得教授回复，再完成研讨。');await this.advance();});}
 buildProject(){return this.run(async()=>{await this.sync();if(this.state.quest.status!=='lab')return;await this.advance();});}
 completeTask(id,done){return this.run(async()=>{await this.client.updateProgress(this.state.sessionId,id,done?'done':'pending');await this.sync();});}
 enter(id,position){this.state.spaceId=id;if(position)this.state.position=position;this.changed();}
 reset(){return this.newProject('新项目');}
}
