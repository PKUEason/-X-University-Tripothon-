import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Window} from 'happy-dom';
import {ConnectedSession} from '../src/service.js';
import {createConversationUI} from '../src/conversation.js';
const html=(await readFile(new URL('../index.html',import.meta.url),'utf8')).replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'').replace(/<link\b[^>]*>/g,'');
function fixture(){
 const window=new Window(),document=window.document;document.write(html);
 const values=new Map(),storage={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};
 let status='created',goal='',space='gate',ui;const messages=[],calls=[];
 const client={createSession:async input=>{goal=input.goal;return {session_id:'same-project'};},getSession:async()=>({session:{goal},messages:[...messages],roadmap:status==='professor'?{stages:[]}:null}),getQuest:async()=>({status}),advanceQuest:async body=>{calls.push(['scholar',body]);messages.push({role:'user',agent:'scholar',content:body.message},{role:'assistant',agent:'scholar',content:'请选择实物还是仿真，并说明周期。'});status='quest_ready';return {};},streamProfessorChat:async body=>{calls.push(['professor',body]);messages.push({role:'user',agent:'professor',content:body.message},{role:'assistant',agent:'professor',content:'教授继续回答'});return {text:'教授继续回答'};}};
 const session=new ConnectedSession({storage,client,health:async()=>({}),onChange:()=>ui?.render()});
 ui=createConversationUI({document,session,getSpace:()=>space});ui.render();
 return {document,window,session,ui,client,calls,storage,messages,setSpace:value=>{space=value;ui.render();},setStatus:value=>{status=value;},type(selector,text){const input=document.querySelector(selector);input.value=text;input.dispatchEvent(new window.Event('input'));},submit(selector){return document.querySelector(selector).onsubmit({preventDefault(){}});}};
}

test('actual goal form transitions to blank reply composer under named Scholar and sends consecutive replies to same project',async()=>{
 const f=fixture(),$=s=>f.document.querySelector(s);
 assert.equal($('#goal-form').hidden,false);assert.equal($('#chat-form').hidden,true);
 f.type('#goal','柔性机器人，一天一小时');await f.submit('#goal-form');
 assert.equal($('#goal-form').hidden,true);assert.equal($('#chat-form').hidden,false);assert.equal($('#message').tagName,'TEXTAREA');assert.equal($('#message').value,'');assert.equal($('#goal').value,'');assert.equal(f.session.state.draftGoal,'');assert.equal($('#reply-label').textContent,'回复 Scholar');assert.match($('#chat-history').textContent,/Scholar · 目标导师/);
 assert.equal($('#chat-form').parentElement.id,'agent-panel');assert.equal($('#agent-scroll').contains($('#chat-history')),true);assert.equal($('#agent-scroll').contains($('#chat-form')),false);
 assert.equal($('#send-reply').disabled,true);
 for(const reply of ['先做仿真，我会 Python','希望两周做完，先验证抓取动作']){f.type('#message',reply);assert.equal($('#send-reply').disabled,false);await f.submit('#chat-form');assert.equal($('#message').value,'');assert.equal(f.document.activeElement.id,'message');assert.equal(f.session.state.quest.status,'quest_ready');}
 assert.equal(f.calls.length,3);assert.ok(f.calls.every(([agent,body])=>agent==='scholar'&&body.session_id==='same-project'&&body.message));assert.equal(f.calls[1][1].message,'先做仿真，我会 Python');assert.equal(f.session.state.roadmap,null);assert.match($('#chat-history').textContent,/希望两周做完/);
 await f.window.happyDOM.close();
});

test('failed reply stays editable and retry never creates a new project',async()=>{
 const f=fixture(),$=s=>f.document.querySelector(s);f.type('#goal','柔性机器人');await f.submit('#goal-form');f.type('#message','我会 Python');f.client.advanceQuest=async()=>{throw Error('网络中断');};await f.submit('#chat-form');assert.equal($('#message').value,'我会 Python');assert.equal($('#message').disabled,false);assert.equal($('#send-reply').disabled,false);assert.equal(f.session.state.sessionId,'same-project');assert.equal(f.session.state.draftScholarReply,'我会 Python');await f.window.happyDOM.close();
});

test('Scholar and Professor keep separate drafts and reply to the visible agent',async()=>{
 const f=fixture(),$=s=>f.document.querySelector(s);f.type('#goal','柔性机器人');await f.submit('#goal-form');f.type('#message','Scholar 草稿');f.setStatus('professor');await f.session.recover();f.setSpace('office');assert.equal($('#reply-label').textContent,'回复 Professor');assert.equal($('#message').value,'');f.type('#message','Professor 草稿');f.setSpace('gate');assert.equal($('#message').value,'Scholar 草稿');f.setSpace('office');assert.equal($('#message').value,'Professor 草稿');await f.submit('#chat-form');assert.equal(f.calls.at(-1)[0],'professor');assert.equal(f.calls.at(-1)[1].message,'Professor 草稿');assert.equal(f.session.state.draftScholarReply,'Scholar 草稿');assert.match($('#chat-history').textContent,/Professor · 研究导师/);await f.window.happyDOM.close();
});

test('existing screenshot state hides stale goal draft and shows empty reply after restore',async()=>{
 const f=fixture(),$=s=>f.document.querySelector(s);f.session.state.goal='旧的目标';f.session.state.draftGoal='旧的目标';f.session.state.quest.status='clarifying';f.session.state.messages=[{role:'assistant',agent:'scholar',content:'请确认三个问题'}];f.ui.restore();f.ui.render();assert.equal($('#goal-form').hidden,true);assert.equal($('#chat-form').hidden,false);assert.equal($('#message').value,'');assert.equal($('#message').disabled,false);assert.match($('#chat-history').textContent,/请确认三个问题/);f.setSpace('library');assert.equal($('#chat-form').hidden,true);await f.window.happyDOM.close();
});

test('latest assistant questions become a reply card; old answers stay expandable and expansion survives rendering',async()=>{
 const f=fixture(),$=s=>f.document.querySelector(s);
 f.session.state.goal='柔性机器人';f.session.state.messages=[
 {agent:'scholar',role:'user',content:'先讨论方向'},
 {agent:'scholar',role:'assistant',content:'你想研究哪一类机器人？'},
 {agent:'scholar',role:'user',content:'柔性机器人'},
 {agent:'scholar',role:'assistant',content:'可以先做**小原型**。\n\n我还想确认三点：\n\n1. **形态**：你想做实物还是仿真？\n2. **基础**：你会 Python 吗？\n3. **时间**：你希望多久完成？'}];
 f.ui.render();assert.equal(f.document.querySelectorAll('.question-list > li').length,3);assert.equal(f.document.querySelectorAll('.question-card').length,1);assert.match($('#reply-context').textContent,/3 个问题/);assert.doesNotMatch($('#chat-history').textContent,/\*\*/);assert.equal($('.conversation-archive').open,false);
 $('.conversation-archive').open=true;f.ui.render();assert.equal($('.conversation-archive').open,true);$('.reply-shortcut').click();assert.equal(f.document.activeElement.id,'message');
 f.session.state.messages.push({agent:'scholar',role:'user',content:'选择仿真'});f.ui.render();assert.equal($('.question-card'),null,'answered historical questions must not remain pending');assert.equal($('#chat-form').hidden,false);
 await f.window.happyDOM.close();
});

test('streamed assistant Markdown uses the same rendering and leaves the composer present',async()=>{
 const f=fixture(),$=s=>f.document.querySelector(s);f.session.state.goal='测试目标';f.session.busy=true;f.session.stream='**建议**：先做仿真。';f.ui.render();assert.equal($('#response strong').textContent,'建议');assert.equal($('#chat-form').hidden,false);assert.equal($('#message').disabled,true);f.session.busy=false;f.ui.render();assert.equal($('#message').disabled,false);await f.window.happyDOM.close();
});

test('both composers send on Enter, preserve Shift+Enter, and ignore IME confirmation and key repeat',async()=>{
 const f=fixture();for(const [selector,form] of [['#goal','#goal-form'],['#message','#chat-form']]){let sends=0;f.document.querySelector(form).requestSubmit=()=>sends++;const input=f.document.querySelector(selector);
 for(const event of [{key:'Enter',shiftKey:true},{key:'Enter',isComposing:true},{key:'Enter',keyCode:229},{key:'Enter',repeat:true}])input.onkeydown({...event,preventDefault(){}});assert.equal(sends,0);let prevented=false;input.onkeydown({key:'Enter',preventDefault(){prevented=true;}});assert.equal(sends,1);assert.ok(prevented);f.session.busy=true;input.onkeydown({key:'Enter',preventDefault(){}});assert.equal(sends,1);f.session.busy=false;}await f.window.happyDOM.close();
});
