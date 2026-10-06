// Confirm with the server first; a failed save must never celebrate completion.
export async function updateTaskWithFeedback({document,session,id,done}){
 const projectId=session.state.projectId;
 const ok=await session.completeTask(id,done);
 if(!ok||session.state.projectId!==projectId)return false;
 for(const input of document.querySelectorAll('input[data-task-id]')){
  if(input.dataset.taskId!==id)continue;
  input.checked=done;
  const row=input.closest('.task');row?.classList.toggle('task-done',done);
  if(done&&document.body.dataset.reduceMotion!=='true'&&!document.defaultView.matchMedia('(prefers-reduced-motion: reduce)').matches){
   row?.classList.add('task-celebrate');
   input.animate?.([{transform:'scale(1)'},{transform:'scale(1.35)',offset:.4},{transform:'scale(1)'}],{duration:420,easing:'ease-out'});
   setTimeout(()=>row?.classList.remove('task-celebrate'),850);
  }
 }
 const host=document.querySelector('#tasks-panel[open]')||document.querySelector('#agent-panel[open]');
 if(host){host.querySelector('.completion-note')?.remove();const note=document.createElement('div');note.className='completion-note';note.setAttribute('role','status');note.textContent=done?'✓ 已完成一项任务':'已取消完成标记';host.append(note);setTimeout(()=>note.remove(),1800);}
 return true;
}
