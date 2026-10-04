import {Lexer} from './markdown-vendor.js';

// Only create known DOM nodes. Markdown HTML is displayed as text, never executed.
// Keeping the token tree also lets us group questions without rewriting AI content.
export function tokenize(text){
 const source=String(text??'').replace(/\r\n?/g,'\n');
 // Accept the common Chinese numbered-list spelling without touching code fences.
 let fence=false;
 const normalized=source.split('\n').map(line=>{
  if(/^\s*(```|~~~)/.test(line))fence=!fence;
  return fence?line:line.replace(/^(\s*)(\d+)[）．、]\s*/,'$1$2. ');
 }).join('\n');
 return Lexer.lex(normalized,{gfm:true,breaks:true});
}

export function safeLink(value){
 try{const url=new URL(value);return ['https:','http:'].includes(url.protocol)?url.href:null;}catch{return null;}
}

export function renderRichText(parent,value,{inline=false}={}){
 parent.classList.add('rich-text');
 const tokens=Array.isArray(value)?value:inline?Lexer.lexInline(String(value??''),{gfm:true,breaks:true}):tokenize(value);
 appendTokens(parent,tokens);
 return parent;
}

function appendTokens(parent,tokens){
 const doc=parent.ownerDocument;
 const node=(tag,token,children=token.tokens)=>{const el=doc.createElement(tag);parent.append(el);if(children)appendTokens(el,children);else el.textContent=token.text??'';return el;};
 for(const token of tokens??[]){switch(token.type){
  case 'space':break;
  case 'heading':node('h'+Math.min(6,token.depth+2),token);break;
  case 'paragraph':node('p',token);break;
  case 'text':if(token.tokens)appendTokens(parent,token.tokens);else parent.append(doc.createTextNode(token.text??''));break;
  case 'strong':node('strong',token);break;
  case 'em':node('em',token);break;
  case 'del':node('del',token);break;
  case 'escape':case 'html':parent.append(doc.createTextNode(token.text??token.raw??''));break;
  case 'codespan':node('code',token,null);break;
  case 'code':{const pre=node('pre',{text:''},null);const code=doc.createElement('code');code.textContent=token.text;pre.append(code);break;}
  case 'br':node('br',{text:''},null);break;
  case 'hr':node('hr',{text:''},null);break;
  case 'blockquote':node('blockquote',token);break;
  case 'link':{const href=safeLink(token.href);const a=node(href?'a':'span',token);if(href){a.href=href;a.target='_blank';a.rel='noopener noreferrer';}break;}
  case 'image':{const a=node(safeLink(token.href)?'a':'span',{text:token.text||'图片链接'},null);if(safeLink(token.href)){a.href=safeLink(token.href);a.target='_blank';a.rel='noopener noreferrer';}break;}
  case 'list':{
   const list=node(token.ordered?'ol':'ul',{text:''},null);if(token.ordered&&token.start!==1)list.start=token.start;
   for(const item of token.items){const li=doc.createElement('li');list.append(li);if(item.task){const mark=doc.createElement('span');mark.className='markdown-check';mark.textContent=item.checked?'☑ ':'☐ ';li.append(mark);}appendTokens(li,item.tokens);}
   break;
  }
  case 'table':{
   const wrap=node('div',{text:''},null);wrap.className='table-scroll';wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','可横向滚动的表格');
   const table=doc.createElement('table');wrap.append(table);
   for(const [tag,rows] of [['thead',[token.header]],['tbody',token.rows]]){const section=doc.createElement(tag);table.append(section);for(const cells of rows){const tr=doc.createElement('tr');section.append(tr);for(const [i,cell] of cells.entries()){const td=doc.createElement(tag==='thead'?'th':'td');if(tag==='thead')td.scope='col';if(token.align[i])td.style.textAlign=token.align[i];appendTokens(td,cell.tokens);tr.append(td);}}}
   break;
  }
  default:parent.append(doc.createTextNode(token.raw??token.text??''));
 }}
}

export function groupQuestions(text){
 const tokens=tokenize(text),questions=[],answer=[];
 let prompted=false;
 const asks=value=>/[?？]/.test(value)&&(/你|您|是否|能否|哪|多久|多少|what|which|would you|can you/i.test(value)||prompted);
 for(const token of tokens){
  if(['paragraph','heading'].includes(token.type)&&/请.*(?:回答|确认|选择|补充)|(?:还|需要|想|先).*(?:确认|问)|几个问题|以下.*问题/i.test(token.text??''))prompted=true;
  if(token.type==='list'){
   // Do not promote fenced code, nested examples or task lists to questions.
   const rest=[];for(const item of token.items){
    if(!item.task&&asks(item.text)&&!item.tokens.some(t=>t.type==='code'))questions.push(item.tokens);
    else rest.push(item);
   }
   if(rest.length)answer.push({...token,items:rest});
  }else if(token.type==='paragraph'&&asks(token.text??''))questions.push([token]);
  else answer.push(token);
 }
 return {questions,answer,tokens};
}
