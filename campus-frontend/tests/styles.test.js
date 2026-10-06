import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Window} from 'happy-dom';
import {validateStyles} from '../scripts/validate-styles.mjs';

const css=(await readFile(new URL('../style.css',import.meta.url),'utf8'))+'\n'+(await readFile(new URL('../glass.css',import.meta.url),'utf8'));
const html=(await readFile(new URL('../index.html',import.meta.url),'utf8')).replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'').replace(/<link\b[^>]*>/g,'');

test('stylesheet parses and accidental JavaScript overwrite fails validation',async()=>{
 await validateStyles(css);
 await assert.rejects(validateStyles(await readFile(new URL('../src/app.js',import.meta.url),'utf8')));
 await assert.rejects(validateStyles(''));
});

for(const width of [1440,390])test(`actual stylesheet retains campus layout and reply composer at ${width}px`,async()=>{
 const window=new Window({width,height:900});
 try{
  const document=window.document;document.write(html);
  const style=document.createElement('style');style.textContent=css;document.head.append(style);
  const $=s=>document.querySelector(s),computed=s=>window.getComputedStyle($(s));
  $('#projects-panel').setAttribute('open','');
  $('#project-list').innerHTML='<article class="project-option selected"><h3>当前项目</h3></article>';
  assert.equal(computed('body').marginTop,'0px');
  assert.equal(computed('body').overflow,'hidden');
  assert.equal(computed('#world').position,'fixed');
  assert.equal(computed('header').position,'absolute');
  assert.equal(computed('#project-list').display,'grid');
  assert.equal(computed('#project-list').gridTemplateColumns.replace(/\s/g,''),width===390?'1fr':'repeat(2,minmax(0,1fr))');
  assert.match(computed('#projects-panel').backgroundImage,/linear-gradient/);
  assert.equal(computed('#projects-panel').borderRadius,width===390?'20px':'24px');
  assert.equal(computed('.project-option.selected').borderTopWidth,'2px');
  $('#agent-panel').setAttribute('open','');$('#chat-form').hidden=false;
  assert.equal(computed('#agent-panel').display,'flex');
  assert.equal(computed('#agent-panel').flexDirection,'column');
  assert.equal(computed('#agent-scroll').overflowY,'auto');
  assert.equal(computed('#chat-form').flexShrink,'0');
  $('#chat-form').hidden=true;
  assert.equal(computed('#chat-form').display,'none');
 }finally{await window.happyDOM.close();}
});

test('conversation hierarchy uses fixed header/composer and scrollable content on short mobile screens',async()=>{
 const window=new Window({width:390,height:600});try{
 const d=window.document;d.write(html);const style=d.createElement('style');style.textContent=css;d.head.append(style);
 const panel=d.querySelector('#agent-panel');panel.setAttribute('open','');panel.dataset.conversation='true';d.querySelector('#chat-form').hidden=false;
 const get=s=>window.getComputedStyle(d.querySelector(s));
 assert.equal(d.querySelector('.panel-heading').parentElement,panel);assert.equal(d.querySelector('#chat-form').parentElement,panel);assert.equal(get('.panel-heading').flexShrink,'0');assert.equal(get('#chat-form').flexShrink,'0');assert.equal(get('#agent-scroll').minHeight,'0');assert.equal(get('#agent-scroll').overflowY,'auto');assert.equal(get('#agent-panel > .disclaimer').display,'none');
 const sample=d.createElement('article');sample.className='message-card';sample.innerHTML='<div class="rich-text"><p><strong>重点</strong> 与正文</p><ol><li>第一项</li></ol></div>';d.querySelector('#chat-history').append(sample);
 assert.equal(get('#chat-history .rich-text strong').display,'inline');assert.equal(get('.rich-text ol').listStyleType,'decimal');assert.equal(get('.rich-text').whiteSpace,'normal');
 }finally{await window.happyDOM.close();}
});
