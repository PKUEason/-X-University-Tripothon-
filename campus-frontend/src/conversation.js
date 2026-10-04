import {renderRichText,groupQuestions} from './rich-text.js';
// One reply composer beneath the conversation, addressed to the visible agent.
export function createConversationUI({document,session,getSpace}){
 const $=selector=>document.querySelector(selector);
 const keyFor=space=>space==='gate'?'draftScholarReply':'draftMessage';
 const agentFor=space=>space==='gate'?'scholar':space==='office'?'professor':null;
 const nameFor=agent=>agent==='scholar'?'Scholar':'Professor';
 let viewKey='';
 const historyExpansion=new Map();
 function scrollLatest(){const scroller=$('#agent-scroll'),target=$('#response').lastElementChild?$('#response'):$('#chat-history').lastElementChild;scroller.scrollTop=target?Math.max(0,target.offsetTop+target.offsetHeight-scroller.clientHeight+32):0;}
 function restore(){const key=keyFor(getSpace());$('#goal').value=session.state.draftGoal||'';$('#message').value=session.state[key]||'';}
 function render(){
  const s=session.state,space=getSpace(),agent=agentFor(space),name=nameFor(agent);
  const messages=agent?s.messages.filter(m=>m.agent===agent):[];
  const started=messages.length>0||!!s.goal;
  const visible=space==='gate'?started:space==='office'&&!!s.roadmap;
  const scroller=$('#agent-scroll'),nearBottom=scroller.scrollHeight-scroller.scrollTop-scroller.clientHeight<80;
  const nextKey=s.projectId+':'+space,changedView=nextKey!==viewKey;viewKey=nextKey;
  $('#agent-panel').dataset.conversation=String(visible);
  $('#goal-form').hidden=space!=='gate'||started;
  $('#goal').disabled=session.busy;$('#submit-goal').disabled=session.busy;
  $('#chat-form').hidden=!visible;
  $('#reply-label').textContent='回复 '+name;
  $('#reply-context').textContent=agent==='scholar'?'直接回答上面 Scholar 的问题，会接着本项目的对话继续。':'直接回答上面 Professor 的问题，会接着本项目的研讨继续。';
  const input=$('#message'),draft=s[keyFor(space)]||'';
  if(input.value!==draft)input.value=draft;
  input.disabled=session.busy;input.placeholder='在这里回答 '+name+' 的问题，或继续追问…';
  const send=$('#send-reply');send.textContent=session.busy?'正在回复…':'发送回复 ↗';send.disabled=session.busy||!input.value.trim();
  const history=$('#chat-history');
  const previous=history.querySelector('.conversation-archive');
  if(previous)historyExpansion.set(previous.dataset.view,previous.open);
  history.replaceChildren();
  const latestStart=messages.at(-1)?.role==='assistant'?Math.max(0,messages.length-2):Math.max(0,messages.length-1);
  let archive;
  if(latestStart){
   archive=document.createElement('details');archive.className='conversation-archive';archive.dataset.view=nextKey;archive.open=historyExpansion.get(nextKey)??false;
   const summary=document.createElement('summary');summary.textContent=`查看之前的对话 · ${latestStart} 条消息`;archive.append(summary);history.append(archive);
  }
  let pendingQuestions=0;
  for(const [index,m] of messages.entries()){
   const empty=m.role==='assistant'&&!m.content?.trim(),latest=index===messages.length-1&&m.role==='assistant';
   const row=document.createElement('article');row.className='message-card';row.dataset.role=m.role;
   const meta=document.createElement('div');meta.className='message-meta';
   const avatar=document.createElement('span');avatar.className='message-avatar';avatar.textContent=m.role==='user'?'你':name[0];avatar.setAttribute('aria-hidden','true');
   const author=document.createElement('strong');author.textContent=m.role==='user'?'你的回复':name==='Scholar'?'Scholar · 目标导师':'Professor · 研究导师';
   const badge=document.createElement('span');badge.className='message-kind';badge.textContent=m.role==='user'?'我的想法':'导师回复';meta.append(avatar,author,badge);
   const body=document.createElement('div');body.className='message-body';
   const grouped=latest&&!empty?groupQuestions(m.content):null;
   const content=empty?'这次回复没有生成正文。你的问题已保留，可以重试。':grouped?.questions.length?grouped.answer:m.content;
   renderRichText(body,content);row.append(meta,body);
   (index<latestStart?archive:history).append(row);
   if(latest&&grouped?.questions.length){
    pendingQuestions=grouped.questions.length;
    const card=document.createElement('section');card.className='question-card';card.setAttribute('aria-labelledby','questions-title');
    const label=document.createElement('div');label.className='section-kicker';label.textContent='轮到你了';
    const title=document.createElement('h3');title.id='questions-title';title.textContent=`需要你回答的 ${pendingQuestions} 个问题`;
    const hint=document.createElement('p');hint.className='section-note';hint.textContent='可以一次回答，也可以先从最确定的一项开始。';
    const list=document.createElement('ol');list.className='question-list';
    for(const [i,tokens] of grouped.questions.entries()){const item=document.createElement('li');const number=document.createElement('span');number.className='question-number';number.textContent=String(i+1).padStart(2,'0');number.setAttribute('aria-hidden','true');const text=document.createElement('div');renderRichText(text,tokens);item.append(number,text);list.append(item);}
    const focus=document.createElement('button');focus.type='button';focus.className='reply-shortcut';focus.textContent='在下方回复 ↓';focus.disabled=session.busy;focus.onclick=()=>$('#message').focus();
    card.append(label,title,hint,list,focus);history.append(card);
   }
   if(empty&&!session.busy){const question=messages.slice(0,index).findLast(item=>item.role==='user')?.content;if(question){const retry=document.createElement('button');retry.textContent='重试这条问题';retry.onclick=()=>agent==='scholar'?session.clarify(question):session.discuss(question);row.append(retry);}}
  }
  $('#reply-context').textContent=pendingQuestions?`上方有 ${pendingQuestions} 个问题等待你的回应；也可以补充想法或继续追问。`:'补充你的想法、回答导师，或提出新的问题。';
  $('#agent-panel').dataset.awaitingReply=String(pendingQuestions>0);
  const response=$('#response');response.replaceChildren();
  if(session.busy&&session.stream&&agent){
   const label=document.createElement('div');label.className='section-kicker';label.textContent=name+' 正在回复';response.append(label);
   const body=document.createElement('div');renderRichText(body,session.stream);response.append(body);
  }
  if(changedView||nearBottom)scrollLatest();
 }
 async function send(kind){
  if(session.busy)return;
  const space=getSpace(),agent=kind==='goal'?'scholar':agentFor(space);
  if(!agent)return;
  const input=kind==='goal'?$('#goal'):$('#message'),key=kind==='goal'?'draftGoal':keyFor(space),text=input.value.trim();if(!text)return;
  const state=session.state;state[key]=input.value;session.persist();
  const ok=agent==='scholar'?await session.clarify(text):await session.discuss(text);
  if(ok&&state[key]?.trim()===text){state[key]='';session.persist();}
  if(session.state.projectId!==state.projectId||getSpace()!==space)return;
  if(ok){restore();render();scrollLatest();if(!$('#chat-form').hidden)$('#message').focus();}
 }
 $('#goal').oninput=()=>{session.state.draftGoal=$('#goal').value;session.persist();};
 $('#message').oninput=()=>{session.state[keyFor(getSpace())]=$('#message').value;session.persist();$('#send-reply').disabled=session.busy||!$('#message').value.trim();};
 $('#goal-form').onsubmit=e=>{e.preventDefault();return send('goal');};
 $('#chat-form').onsubmit=e=>{e.preventDefault();return send('reply');};
 $('#message').onkeydown=e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)&&!e.isComposing){e.preventDefault();$('#chat-form').requestSubmit();}};
 return {render,restore,scrollLatest};
}
