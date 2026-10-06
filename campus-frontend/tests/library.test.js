import test from 'node:test';
import assert from 'node:assert/strict';
import {Window} from 'happy-dom';
import {renderLibrary} from '../src/library.js';
const result=(overrides={})=>({retrieval_version:3,query:'AI 硬件',documents:[],notice:'本地资料库尚未覆盖',arxiv_status:'ok',arxiv_papers:[{title:'TinyML research',authors:['Alice','Bob'],year:'2025',url:'https://arxiv.org/abs/1234.5678',snippet:'Abstract excerpt'}],...overrides});

test('arXiv papers display even when local coverage is empty; metadata and safe links remain visible',async()=>{
 const w=new Window();try{const parent=w.document.body;renderLibrary(parent,result());
 assert.match(parent.textContent,/本地资料库尚未覆盖/);assert.match(parent.textContent,/arXiv 相关论文/);assert.match(parent.textContent,/Alice、Bob/);assert.match(parent.textContent,/2025/);assert.match(parent.textContent,/Abstract excerpt/);assert.equal(parent.querySelector('a').href,'https://arxiv.org/abs/1234.5678');assert.equal(parent.querySelector('[role="status"]').dataset.arxivStatus,'ok');
 }finally{await w.happyDOM.close();}
});

test('empty, failed, disabled, and mock searches are distinct and never display stale papers',async()=>{
 const w=new Window();try{for(const [status,label] of [['ok','没有命中'],['failed','暂时无法连接'],['disabled','尚未启用'],['mock','未执行联网']]){
 w.document.body.replaceChildren();renderLibrary(w.document.body,result({arxiv_status:status,arxiv_papers:status==='ok'?[]:result().arxiv_papers}));assert.match(w.document.body.textContent,new RegExp(label));assert.equal(w.document.body.querySelectorAll('a').length,0);
 }}finally{await w.happyDOM.close();}
});

test('external paper text cannot inject markup or executable links',async()=>{
 const w=new Window();try{renderLibrary(w.document.body,result({arxiv_papers:[{title:'<img src=x onerror=alert(1)>',url:'javascript:alert(1)',snippet:'<script>bad()</script>',authors:[],year:''}]}));assert.equal(w.document.querySelectorAll('script,img,a').length,0);assert.match(w.document.body.textContent,/<script>/);}finally{await w.happyDOM.close();}
});

test('old cache does not silently pretend that arXiv has already searched',async()=>{
 const w=new Window();try{renderLibrary(w.document.body,result({retrieval_version:2}));assert.match(w.document.body.textContent,/资料版本已更新/);assert.equal(w.document.querySelectorAll('a').length,0);}finally{await w.happyDOM.close();}
});

test('editable paper keywords submit without changing the goal and disable during requests',async()=>{
 const w=new Window();try{let submitted;const body=w.document.body;
 renderLibrary(body,result({arxiv_query:'TinyML'}),{onSearch:value=>{submitted=value;}});
 const input=body.querySelector('#paper-query');assert.equal(input.value,'TinyML');input.value='keyword spotting';body.querySelector('form').onsubmit({preventDefault(){}});assert.equal(submitted,'keyword spotting');assert.match(body.textContent,/检索依据：AI 硬件/);
 body.replaceChildren();renderLibrary(body,result({arxiv_status:'needs_query'}),{busy:true,onSearch(){throw Error('must not submit');}});assert.ok(body.querySelector('input').disabled);assert.ok(body.querySelector('button').disabled);assert.match(body.textContent,/填写英文主题/);
 }finally{await w.happyDOM.close();}
});

test('v4 renders unified local, paper, web and learning resources with honest source status',async()=>{
 const w=new Window();try{renderLibrary(w.document.body,{retrieval_version:4,query:'TinyML',notice:'统一检索',sources:{local:'ok',arxiv:'ok',web:'ok',resource:'partial'},results:[{source:'arxiv',type:'paper',title:'Paper',url:'https://arxiv.org/abs/1234',authors:['Alice'],year:'2026'},{source:'web',type:'webpage',title:'Tutorial',url:'https://example.com'},{source:'course',type:'course',title:'Course',url:'https://example.com/course'},{source:'book',type:'book',title:'Book',url:'javascript:bad()'}]});assert.equal(w.document.querySelectorAll('.knowledge-node').length,4);assert.equal(w.document.querySelectorAll('a').length,3);assert.match(w.document.body.textContent,/课程与书籍 · 部分可用/);assert.match(w.document.body.textContent,/Alice/);assert.doesNotMatch(w.document.body.textContent,/暂不搜索网页教程/);}finally{await w.happyDOM.close();}
});
