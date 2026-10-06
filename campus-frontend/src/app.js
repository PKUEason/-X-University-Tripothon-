import {updateTaskWithFeedback} from './task-feedback.js';
import {paintIdentity} from './identity.js';
import {createCampusShell} from './shell.js';
import {ConnectedSession,nextSpace,tasksIn} from './service.js';
import {createWorld} from './world.js';
import {createStudentPreview} from './student.js';
import {spaces} from './campus.js';
import {createConversationUI} from './conversation.js';
import {taskProgress,projectStatus,renderTaskOverview} from './tasks.js';
import {createSettingsUI} from './settings.js';
import {renderRichText} from './rich-text.js';
import {renderLibrary} from './library.js';
const $=s=>document.querySelector(s);
let shell,preview,world,info={},panelSpace='gate',lastSaved=0,errors=0,storage;
try{storage=localStorage;}catch{storage={getItem:()=>null,setItem:()=>{}};}
const session=new ConnectedSession({storage,onChange:render});
const conversation=createConversationUI({document,session,getSpace:()=>panelSpace});
const preferences=createSettingsUI({document,storage,apply:value=>world?.applySettings(value),resetCamera:()=>{world?.resetCamera();toast('镜头已重置，人物位置保留。');}});
let explored;try{explored=new Set(JSON.parse(storage.getItem('xuni-campus-explored')||'[]').filter(id=>spaces[id]));}catch{explored=new Set();}
const planExpansion=new Map();
const contentExpansion=new Map();let contentViewKey="";
let deletingProjectId=null;
const projectTitle=p=>p.title||p.goal||'新项目';
const stageNames={created:'提出一个目标',clarifying:'与 Scholar 确认目标',quest_ready:'生成你的任务路线',library:'去 Library 建立知识基础',professor:'带着资料，与 Professor 研讨',lab:'在 X Lab 形成行动方案',project_ready:'项目方案已生成'};
const progress={created:0,clarifying:0,quest_ready:0,library:1,professor:2,lab:3,project_ready:4};
const titles={gate:'Scholar · 从一个目标开始',plaza:'Plaza · 你的任务路线',library:'Library · 资料与知识',office:'Professor · 收敛研究问题',lab:'X Lab · 从问题到方案'};
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('visible');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.remove('visible'),4000);}
addEventListener('error',()=>errors++);addEventListener('unhandledrejection',()=>errors++);
const blocked=()=>!!document.querySelector('dialog[open]')||shell?.mode==='home'||!$('#radial-menu').hidden;
function openPanel(id){world?.releaseCursor();world?.stop();if(!$(id).open)$(id).showModal();}
async function showAgent(space=session.state.spaceId){const projectId=session.state.projectId;const fromHome=shell?.mode==='home',returning=fromHome||document.body.dataset.sceneTransition==='true';if(returning){if(fromHome)shell.setView('third');const ready=await world?.whenSceneReady();if(ready===false)return;}if(session.state.projectId!==projectId||(returning&&shell?.mode!=='third'))return;panelSpace=space;render();openPanel('#agent-panel');conversation.scrollLatest();}
function enter(space){session.enter(space);if(!explored.has(space)){explored.add(space);try{storage.setItem('xuni-campus-explored',JSON.stringify([...explored]));}catch{}toast('探索记录 +1 · '+spaces[space].name);render();}}
async function interact(space=session.state.spaceId){showAgent(space);if(!session.busy&&((space==='library'&&session.state.roadmap)||(space==='office'&&session.state.quest.status==='professor')))await session.visit(space);}
function navigate(target){shell?.setView('third');$('#agent-panel').close();world?.guideTo(target);if(!$('#agent-panel').open)toast('路线已标记 · 使用 WASD / 方向键前往 '+spaces[target].name+'，抵达后按 E 互动');}
function next(){const target=nextSpace(session.state.quest.status);if(session.state.spaceId===target)interact(target);else if(session.state.spaceId==='gate'&&target==='library')navigate('plaza');else navigate(target);}
function element(tag,text,cls){const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e;}
function rich(tag,text,cls){const e=element(tag,'',cls);renderRichText(e,text,{inline:['h3','h4','li','span','a'].includes(tag)});return e;}
function list(parent,title,items){if(!items?.length)return;const section=element('section','','content-card');section.append(element('h3',title));const ul=document.createElement('ul');ul.className='plan-list';for(const value of items)ul.append(rich('li',typeof value==='string'?value:JSON.stringify(value)));section.append(ul);parent.append(section);}
function safeUrl(url){try{const value=new URL(url);return ['https:','http:'].includes(value.protocol)?value.href:null;}catch{return null;}}
function references(parent,refs){for(const doc of refs??[]){const card=element('section','','knowledge-node');const href=safeUrl(doc.url);if(href){const a=rich('a',doc.title);a.href=href;a.target='_blank';a.rel='noopener noreferrer';card.append(a);}else card.append(rich('h3',doc.title));if(doc.snippet)card.append(rich('div',doc.snippet));parent.append(card);}}
function renderProjects(){
 const list=$('#project-list');list.replaceChildren();
 if(!session.projects.length)list.append(element('p','还没有项目。在下方填写名称，开始一个新项目。','project-empty'));
 for(const p of session.projects){
  const selected=p.projectId===session.state.projectId,card=element('section','',selected?'project-option selected':'project-option');
  card.append(element('span',selected?'当前项目':'可切换项目','project-label'),element('h3',projectTitle(p)),element('p',p.goal||'等待提出目标'));
  const steps=element('div','','project-stages');for(const [i,name]of ['目标','资料','研讨','方案','行动卡'].entries()){const index=progress[p.quest.status]??0;steps.append(element('span',name,p.quest.status==='project_ready'||i<index?'done':i===index?'active':''));}card.append(steps);
  card.append(element('p',projectStatus(p,stageNames[p.quest.status]??'提出目标'),'stage-label'));
  if(p.roadmap){const taskState=taskProgress(p.roadmap);card.append(element('small',`任务清单 · 已勾选 ${taskState.done} / ${taskState.total} 项`));const view=element('button',taskState.remaining?`查看剩余 ${taskState.remaining} 项任务`:'查看全部任务（已全部勾选）');view.disabled=session.busy;view.onclick=()=>openTasks(p.projectId);card.append(view);}
  const button=element('button',selected?'回到当前项目':'切换到此项目');button.disabled=session.busy;button.onclick=async()=>{if(!session.switchProject(p.projectId))return;restoreDrafts();$('#projects-panel').close();await session.recover();const target=nextSpace(session.state.quest.status);showAgent(target);};card.append(button);list.append(card);
 }
 for(const [index,p] of session.projects.entries()){
  const remove=element('button','删除项目','danger');remove.disabled=session.busy;remove.setAttribute('aria-label','删除项目：'+projectTitle(p));
  remove.onclick=()=>{deletingProjectId=p.projectId;$('#delete-project-name').textContent=projectTitle(p);$('#delete-project-error').textContent='';openPanel('#delete-project-panel');$('#cancel-delete-project').focus();};
  list.children[index].append(remove);
 }
 $('#project-busy').textContent=session.busy?(session.status||'正在处理请求，请稍后再切换、新建或删除项目。'):session.error;$('#create-project').disabled=session.busy;
}
function restoreDrafts(){conversation.restore();}
async function openTasks(id=session.state.projectId){if(session.busy)return;if(!session.switchProject(id))return;restoreDrafts();$('#projects-panel').close();$('#agent-panel').close();openPanel('#tasks-panel');renderTaskOverview({document,session});await session.recover();renderTaskOverview({document,session});}
function openProjects(){world?.stop();renderProjects();openPanel('#projects-panel');}
function openStudent(){const p=session.profile;$('#nickname').value=p?.nickname||'';document.querySelectorAll('[name="gender"]').forEach(r=>r.checked=r.value===p?.gender);document.querySelectorAll('[name="identity"]').forEach(r=>r.checked=r.value===(p?.role||'learner'));updateProfilePreview();$('#cancel-profile').hidden=!p;$('#enter-campus').textContent=p?'保存校园身份':'开始校园活动 →';preview?.setProfile(p||{gender:'male'});openPanel('#student-panel');}
function render(){
 const s=session.state,q=s.quest,status=q.status,pending=session.busy,target=nextSpace(status),step=progress[status]??0;
 const mode=session.mode?.mock_mode?'后端演示模式':s.fallbacks.length?'已连接 · 含降级示例':session.mode?'Agent 已连接':'正在连接 Agent';
 $('#student-button').textContent=session.profile?.nickname||'学生资料';$('#active-project-name').textContent=projectTitle(s)+' ▾';$('#panel-project').textContent='当前项目 · '+projectTitle(s);if($('#projects-panel').open)renderProjects();
 if(!session.projects.length)$('#active-project-name').textContent='尚未创建项目 ▾';
 $('#mode').textContent=mode;$('#panel-mode').textContent=mode;
 $('#quest-title').textContent=projectStatus(s,stageNames[status]??status);$('#goal-summary').textContent=s.goal||'从想学、想研究、想做的一件事开始。';$('#step-number').textContent=(step+1)+' / 5';
 document.querySelectorAll('#steps li').forEach((li,i)=>{li.classList.toggle('active',status!=='project_ready'&&i===step);li.classList.toggle('done',status==='project_ready'||i<step);});
 $('#next').textContent=s.spaceId===target?'打开 '+spaces[target].name+' 面板 ↗':s.spaceId==='gate'&&target==='library'?'标记前往 Plaza 的路线 →':'标记前往 '+spaces[target].name+' 的路线 →';
 if(status==='project_ready')$('#next').textContent='查看项目行动卡 ↗';
 const taskState=taskProgress(s.roadmap);$('#all-tasks-button').hidden=!s.roadmap;$('#all-tasks-button').disabled=pending;$('#all-tasks-button').textContent=`任务清单 · 已勾选 ${taskState.done}/${taskState.total} · ${taskState.remaining?'剩余 '+taskState.remaining+' 项':'已全部勾选'}`;
 $('#quest-feedback').textContent=session.error?'连接或请求未完成 · 打开面板恢复进度':pending?(session.status||'Agent 正在处理…'):s.fallbacks.length?'部分内容使用后端示例，请查看面板说明。':status==='project_ready'?'规划流程已完成 · 下载行动卡不会改变任务勾选记录':'任务进度与阶段结果由本机后端保存';
 document.querySelectorAll('#radial-items [data-space]').forEach(b=>{const current=b.dataset.space===s.spaceId,visited=explored.has(b.dataset.space);b.dataset.current=String(current);b.dataset.visited=String(visited);if(current)b.setAttribute('aria-current','location');else b.removeAttribute('aria-current');b.querySelector('.region-label small').textContent=`区域 ${b.dataset.sector} · ${current?'当前位置':visited?'已到访':'待探索'}`;});$('#location').textContent='当前位置 · '+spaces[s.spaceId].name;$('#campus-stamps').textContent=`已探索 ${explored.size}/5 处 · 选择区域标记光路`;
 $('#agent-panel').dataset.panelSpace=panelSpace;$('#panel-stage').textContent=['目标澄清','资料收集','研究讨论','制定方案','行动计划'][step]||'提出目标';$('#project-context-drawer').hidden=!s.goal;
 $('#panel-title').textContent=titles[panelSpace];$('#panel-intro').textContent=s.fallbacks.length?'降级说明：'+s.fallbacks.join('；'):'当前目标：'+(s.goal||'等待输入');
 $('#examples').querySelectorAll('button').forEach(b=>b.disabled=pending);
 $('#roadmap-button').hidden=panelSpace!=='gate'||status!=='quest_ready';$('#roadmap-button').disabled=pending;$('#goal-help').hidden=panelSpace!=='gate'||(!s.roadmap&&status!=='quest_ready');$('#goal-help').textContent=s.roadmap?'可以继续补充或讨论目标。已有路线和阶段会保留，不会自动重写。':'已经可以生成路线，也可以继续回答或补充要求。确认准备好后再点击生成。';
 $('#request-status').textContent=pending?(session.status||'正在等待 Agent 回复…可关闭面板，任务会继续。'):'';
 $('#error').textContent=session.error;$('#recover').hidden=!session.error;$('#recover').disabled=pending;
 const content=$('#knowledge');
 for(const detail of content.querySelectorAll('details[data-detail]'))contentExpansion.set(contentViewKey+':'+detail.dataset.detail,detail.open);
 contentViewKey=s.projectId+':'+panelSpace;
 const previousPlan=content.querySelector('#lab-guidance');if(previousPlan)planExpansion.set(previousPlan.dataset.session,previousPlan.open);content.replaceChildren();
 if(panelSpace==='gate'||panelSpace==='plaza'){
  if(s.roadmap){const route=element(panelSpace==='gate'?'details':'section','','route-card');if(panelSpace==='gate'){route.dataset.detail='route';route.append(element('summary','查看已生成的任务路线'));}route.append(rich('h3',s.roadmap.title),rich('div',s.roadmap.summary));const stages=element('div','','route-stages');for(const [i,stage] of (s.roadmap.stages??[]).entries()){const card=element('section','','route-stage');card.append(element('span',String(i+1).padStart(2,'0'),'section-kicker'),rich('h4',stage.name),rich('div',stage.objective));stages.append(card);}route.append(stages);content.append(route);}
 }
 if(panelSpace==='library'){
  if(q.library_result)renderLibrary(content,q.library_result,{busy:pending,onSearch:terms=>session.searchPapers(terms)});
  else content.append(element('p',s.roadmap?'进入图书馆后读取与你的目标相关的资料。':'请先在校门生成任务路线。'));
 }
 if(panelSpace==='office'&&!q.professor_result&&status!=='professor'){const card=element('section','','content-card');card.append(element('h3','带着目标和资料，与导师相遇'),element('p','Professor 会帮你收敛可验证的问题。请先完成当前项目的目标与资料准备，下方按钮会带你回到当前阶段。'));content.append(card);}
 if(panelSpace==='plaza'&&!s.roadmap)content.append(element('p','你的探索路线会出现在这里。先与 Scholar 聊聊你想做的事。'));
 if(panelSpace==='office'&&q.professor_result){const refs=element('details','','context-drawer');refs.dataset.detail='references';refs.append(element('summary','研讨参考资料 · '+(q.professor_result.references?.length||0)+' 条'));references(refs,q.professor_result.references);content.append(refs);}
 if(panelSpace==='lab'){
  if(!q.project&&!q.lab_result&&status!=='lab'){const card=element('section','','content-card');card.append(element('h3','先把问题聊清楚，再制定方案'),element('p','X Lab 会将你的资料与研讨结论整理为实践步骤。当前项目还在'+stageNames[status]+'阶段，点击下方按钮继续；你也可以关闭面板，自由探索校园。'));content.append(card);}
  if(q.project){content.append(element('h3','Project Card · 项目行动卡'),element('p','把你的目标、讨论结论和实践步骤汇总成一份行动计划。用它安排下一步、和队友对齐分工，或下载保存；列出的产出物仍需你实际完成。'),rich('h3',q.project.title),rich('div',q.project.summary));list(content,'计划产出',q.project.deliverables);list(content,'建议技术',q.project.tech_stack);list(content,'下一步',q.project.next_steps);}
  if(q.lab_result){const detail=document.createElement('details');detail.id='lab-guidance';detail.dataset.session=s.sessionId;detail.open=planExpansion.get(s.sessionId)??!q.project;detail.append(element('summary','查看完整实践方案'));detail.append(rich('div',q.lab_result.overview));for(const item of q.lab_result.steps??[])detail.append(rich('h3',item.title),rich('div',item.detail));list(detail,'计划交付物',q.lab_result.deliverables);list(detail,'注意事项',q.lab_result.pitfalls);content.append(detail);}
 }
 for(const detail of content.querySelectorAll('details[data-detail]'))detail.open=contentExpansion.get(contentViewKey+':'+detail.dataset.detail)??false;
 const action=$('#space-action');action.hidden=true;action.disabled=pending;action.dataset.action='';
 if(panelSpace==='library'&&s.roadmap){action.hidden=false;action.textContent='按当前项目重新检索资料';action.dataset.action='refresh-library';}
 if(panelSpace==='office'&&status==='professor'){action.hidden=false;action.textContent=q.professor_result?.answer?.trim()?'已完成研讨，准备进入 Lab →':'开始 Professor 研讨';action.dataset.action=q.professor_result?.answer?.trim()?'finish':'office';}
 if(panelSpace==='lab'&&status==='lab'){action.hidden=false;action.textContent='生成实践方案与 Project Card ↗';action.dataset.action='build';}
 $('#panel-next').hidden=panelSpace===target;$('#panel-next').disabled=pending;$('#panel-next').textContent='前往 '+spaces[target].name+' →';
 if($('#tasks-panel').open)renderTaskOverview({document,session});
 $('#export-project').hidden=panelSpace!=='lab'||!q.project;
 $('#next-actions').hidden=!['#roadmap-button','#space-action','#panel-next','#export-project'].some(id=>!$(id).hidden);
 const taskList=$('#task-list');taskList.replaceChildren();
 const tasks=tasksIn(s.roadmap,panelSpace);if(tasks.length)taskList.append(element('h3','实际任务 · 完成后由你勾选'));
 for(const task of tasks){const label=document.createElement('label');label.className='task'+(task.status==='done'?' task-done':'');const input=document.createElement('input');input.type='checkbox';input.checked=task.status==='done';input.disabled=pending;input.dataset.taskId=task.id;input.onchange=()=>updateTaskWithFeedback({document,session,id:task.id,done:input.checked});label.append(input,rich('span',task.title));taskList.append(label);}
 $('#save-status').textContent=s.sessionId?'服务端会话：'+s.sessionId+'。刷新会重新读取任务、对话和阶段结果。':'尚未创建服务端会话，提交目标后建立。';
 $('#recover').textContent=$('#sync-session').textContent=s.sessionMissing?'从本地备份恢复项目':'恢复服务端进度';
 $('#diagnostics').textContent=JSON.stringify({connected:!!session.mode,mock:session.mode?.mock_mode,sessionId:s.sessionId,projectId:s.projectId,profile:session.profile,projectCount:session.projects.length,space:s.spaceId,status,position:s.position,busy:pending,fallbacks:s.fallbacks.length,character:info.character,characterStatus:info.characterStatus,motion:info.motion,fps:info.fps,errors},null,2);
 conversation.render();shell?.render();
 $('#restart').disabled=pending;$('#student-button').disabled=pending;$('#sync-session').disabled=pending;
}
for(const text of ['我有 Python 基础，每天 1 小时，想在两周内做校园导览机器人原型','我有 PyTorch 基础，每天 3 小时，想用两周跑通扩散模型文生图 Demo']){const b=element('button',text);b.type='button';b.onclick=()=>{$('#goal').value=text;session.state.draftGoal=text;session.persist();$('#goal').focus();};$('#examples').append(b);}
$('#roadmap-button').onclick=()=>session.generateRoadmap();
$('#space-action').onclick=async()=>{const action=$('#space-action').dataset.action;if(action==='finish'){if(await session.finishDiscussion())navigate('lab');}else if(action==='build')await session.buildProject();else if(action==='refresh-library')await session.refreshLibrary();else await session.visit(action);};
$('#recover').onclick=$('#sync-session').onclick=()=>session.state.sessionMissing?session.restoreMissingSession():session.recover();
$('#next').onclick=next;$('#panel-next').onclick=()=>navigate(nextSpace(session.state.quest.status));$('#agent-button').onclick=()=>interact();$('#interact').onclick=()=>{if(info.near)interact(info.near);};
document.querySelectorAll('.close').forEach(b=>b.onclick=()=>b.closest('dialog').close());
for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('close',()=>world?.captureCursor?.());
$('#home').onclick=()=>{world?.reset();session.enter('gate',{x:0,z:16});toast('回到校门，任务进度保留。');};
$('#restart').onclick=()=>{$('#settings-panel').close();openProjects();$('#project-name').focus();};
$('#projects-button').onclick=$('#active-project-name').onclick=openProjects;
$('#all-tasks-button').onclick=()=>openTasks();
$('#cancel-delete-project').onclick=()=>$('#delete-project-panel').close();
$('#delete-project-panel').oncancel=e=>{if(session.busy)e.preventDefault();};
$('#confirm-delete-project').onclick=async()=>{
 if(session.busy||!deletingProjectId)return;
 const id=deletingProjectId,p=session.projects.find(p=>p.projectId===id);if(!p)return;
 $('#confirm-delete-project').disabled=true;$('#cancel-delete-project').disabled=true;$('#delete-project-error').textContent='正在删除…';
 const ok=await session.deleteProject(id);
 $('#confirm-delete-project').disabled=false;$('#cancel-delete-project').disabled=false;
 if(ok){planExpansion.delete(p.sessionId);deletingProjectId=null;$('#delete-project-panel').close();$('#agent-panel').close();restoreDrafts();toast('项目已删除');if(!session.projects.length)$('#project-name').focus();}
 else $('#delete-project-error').textContent=session.error;
};
$('#student-button').onclick=openStudent;
$('#student-panel').oncancel=e=>{if(!session.profile)e.preventDefault();};
$('#cancel-profile').onclick=()=>$('#student-panel').close();
function updateProfilePreview(){const role=document.querySelector('[name="identity"]:checked')?.value||'learner';const gender=document.querySelector('[name="gender"]:checked')?.value||'male';const identity=paintIdentity($('#student-panel'),role);$('#preview-role').textContent=identity.label;preview?.setProfile({gender,role});}
$('#student-form').onchange=updateProfilePreview;
$('#student-form').onsubmit=e=>{e.preventDefault();const first=!session.profile;try{session.setProfile({nickname:$('#nickname').value,gender:document.querySelector('[name="gender"]:checked')?.value,role:document.querySelector('[name="identity"]:checked')?.value||'learner'});world?.setStudent(session.profile);$('#profile-error').textContent='';$('#student-panel').close();if(first)openProjects();}catch(error){$('#profile-error').textContent=error.message;}};
$('#new-project-form').onsubmit=e=>{e.preventDefault();const title=$('#project-name').value.trim();if(!title||!session.newProject(title))return;$('#project-name').value='';restoreDrafts();$('#projects-panel').close();showAgent('gate');};
$('#export-project').onclick=()=>{const blob=new Blob([JSON.stringify({goal:session.state.goal,artifact_type:'project_plan',project:session.state.quest.project,guidance:session.state.quest.lab_result,fallbacks:session.state.fallbacks,mock_mode:session.mode?.mock_mode},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='x-university-project-card.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
try{world=createWorld({container:$('#world'),position:session.state.position,profile:session.profile||{gender:'male'},settings:preferences.value,onSpace:enter,onInteract:interact,onArrive:id=>toast('已抵达 '+spaces[id].name+' · 按 E 开始互动'),isBlocked:blocked,onNotice:toast,onAssetStatus(status){const el=$('#library-asset-status');if(el){el.textContent={loading:'正在加载建筑模型…',ready:'建筑模型已加载 · 可旋转查看',error:'模型加载失败，暂显示旧建筑；刷新可重试'}[status];el.dataset.state=status;}},onInfo(value){info=value;const route=$('#route-status');route.hidden=!value.routeTarget;if(value.routeTarget)route.textContent='◈ '+spaces[value.routeTarget].name+' · '+Math.round(value.routeDistance)+' m · 沿光路步行';$('#fps').textContent=value.fps+' FPS';$('#hotspot').hidden=!value.near||blocked();if(value.near)$('#hotspot-label').textContent=spaces[value.near].label;if(Date.now()-lastSaved>1500){lastSaved=Date.now();session.state.position=world.getPosition();session.persist();}}});}catch(e){toast('三维画面无法启动：'+e.message);errors++;}
addEventListener('pagehide',()=>{if(world){session.state.position=world.getPosition();session.persist();}});
try{preview=createStudentPreview($('#student-preview'));}catch{ $('#student-preview').textContent='学生角色将在校园中展示';}
explored.add(session.state.spaceId);restoreDrafts();render();
shell=createCampusShell({document,session,getWorld:()=>world,onNavigate:navigate,onProjects:openProjects,onStudent:openStudent,onSettings:()=>{render();openPanel('#settings-panel');},onAgent:()=>showAgent(nextSpace(session.state.quest.status)),onTasks:()=>openTasks(),toast});
render();
if(new URL(location.href).searchParams.get('view')==='library')shell.setView('library');
if(!session.profile)openStudent();
void session.recover();
