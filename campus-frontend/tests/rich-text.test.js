import test from 'node:test';
import assert from 'node:assert/strict';
import {Window} from 'happy-dom';
import {renderRichText,groupQuestions} from '../src/rich-text.js';

const sample='柔性机器人可以先从**可运行的小原型**开始。\n\n我还想确认三点：\n\n1) **产品形态**：你更想做实物还是仿真？\n2) **工程基础**：你会 Python 还是 Arduino？\n3) **周期**：你希望两周还是一个月完成？';

test('Chinese assistant clarification separates every question while preserving advice and emphasis',async()=>{
 const w=new Window();try{
 const grouped=groupQuestions(sample);assert.equal(grouped.questions.length,3);
 const advice=w.document.createElement('div');renderRichText(advice,grouped.answer);assert.match(advice.textContent,/可运行的小原型/);assert.doesNotMatch(advice.textContent,/产品形态/);
 for(const tokens of grouped.questions){const div=w.document.createElement('div');renderRichText(div,tokens);assert.ok(div.querySelector('strong'));assert.doesNotMatch(div.textContent,/\*\*/);assert.match(div.textContent,/？/);}
 assert.equal(groupQuestions('先安装 Python，再运行例程。').questions.length,0);
 assert.equal(groupQuestions('```python\nprint("你是谁？")\n```').questions.length,0);
 }finally{await w.happyDOM.close();}
});

test('headings, nested lists, tables, code and citations become safe semantic nodes',async()=>{
 const w=new Window();try{
 renderRichText(w.document.body,'## 实施建议\n\n**重点**与*说明*。\n\n1. 第一步\n   - 子任务\n2. 第二步\n\n> 一次只改变一个变量\n\n| 平台 | 难度 |\n| --- | --- |\n| Arduino | 入门 |\n\n```python\nprint("**literal**")\n```\n\n[官方文档](https://example.org/docs)');
 assert.ok(w.document.querySelector('h4'));assert.ok(w.document.querySelector('ol > li > ul'));assert.equal(w.document.querySelectorAll('table th').length,2);assert.equal(w.document.querySelector('pre code').textContent,'print("**literal**")');assert.ok(w.document.querySelector('blockquote'));assert.equal(w.document.querySelector('a').rel,'noopener noreferrer');assert.equal(w.document.querySelector('strong').textContent,'重点');
 }finally{await w.happyDOM.close();}
});

test('raw HTML, malicious URLs and image markup cannot become active content',async()=>{
 const w=new Window();try{
 renderRichText(w.document.body,'<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[坏链接](javascript:alert(1))\n\n![外部图片](https://example.org/track.png)\n\n[数据](data:text/html,bad)');
 assert.equal(w.document.querySelectorAll('script,img,iframe,svg,[onerror]').length,0);
 for(const a of w.document.querySelectorAll('a'))assert.match(a.href,/^https?:/);
 assert.match(w.document.body.textContent,/<script>/);
 }finally{await w.happyDOM.close();}
});

test('streaming partial Markdown never throws and a completed message renders emphasis',async()=>{
 const w=new Window();try{for(let i=1;i<=sample.length;i++){w.document.body.replaceChildren();renderRichText(w.document.body,sample.slice(0,i));}assert.equal(w.document.querySelectorAll('strong').length,4);assert.doesNotMatch(w.document.body.textContent,/\*\*/);}finally{await w.happyDOM.close();}
});

test('escaped asterisks and code remain literal; completed Chinese list markup is formatted',async()=>{
 const w=new Window();try{renderRichText(w.document.body,'1） **测试**：保留 `a * b`\n2） \\*字面星号\\*');assert.equal(w.document.querySelectorAll('ol > li').length,2);assert.equal(w.document.querySelector('code').textContent,'a * b');assert.match(w.document.body.textContent,/\*字面星号\*/);}finally{await w.happyDOM.close();}
});
