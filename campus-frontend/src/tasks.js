import {updateTaskWithFeedback} from './task-feedback.js';
import {renderRichText} from './rich-text.js';
export function taskProgress(roadmap){
 const tasks=(roadmap?.stages??[]).flatMap(stage=>(stage.tasks??[]).map(task=>({...task,stage_id:stage.id,stage_name:stage.name,space:task.space??stage.space})));
 const done=tasks.filter(task=>task.status==='done').length;
 return {tasks,total:tasks.length,done,remaining:tasks.length-done,allDone:tasks.length>0&&done===tasks.length};
}
export function projectStatus(project,fallback){
 if(project.quest.status!=='project_ready')return fallback;
 return taskProgress(project.roadmap).allDone?'规划完成 · 任务已全部勾选':'规划流程已完成';
}
export function renderTaskOverview({document,session}){
 const $=s=>document.querySelector(s),project=session.state,progress=taskProgress(project.roadmap);
 $('#tasks-project').textContent=project.title||project.goal||'当前项目';
 $('#tasks-summary').textContent=progress.total?`已勾选 ${progress.done} / ${progress.total} 项 · 剩余 ${progress.remaining} 项`:'生成路线后，这里会显示全部任务。';
 $('#tasks-explanation').textContent=(project.quest.status==='project_ready'?'规划流程已完成，行动卡已生成。':'这里汇总所有空间的任务。')+'勾选表示你确认该任务已完成；下载行动卡只保存计划，不会替你勾选任务。';
 $('#tasks-error').textContent=session.error;
 const list=$('#all-tasks');list.replaceChildren();
 for(const stage of project.roadmap?.stages??[]){
  if(!stage.tasks?.length)continue;
  const section=document.createElement('section'),heading=document.createElement('h3');renderRichText(heading,stage.name,{inline:true});section.append(heading);
  for(const task of stage.tasks){
   const label=document.createElement('label');label.className='task overview-task'+(task.status==='done'?' task-done':'');
   const input=document.createElement('input');input.type='checkbox';input.checked=task.status==='done';input.disabled=session.busy;input.dataset.taskId=task.id;
   input.onchange=()=>updateTaskWithFeedback({document,session,id:task.id,done:input.checked});
   const text=document.createElement('span'),title=document.createElement('strong');renderRichText(title,task.title,{inline:true});const state=document.createElement('small');state.textContent=task.status==='done'?'已勾选完成':task.status==='in_progress'?'进行中':'待完成';text.append(title,state);
   if(task.deliverable){const deliverable=document.createElement('span');deliverable.className='task-deliverable';renderRichText(deliverable,'完成标准：'+task.deliverable,{inline:true});text.append(deliverable);}
   label.append(input,text);section.append(label);
  }
  list.append(section);
 }
}
