import {renderRichText,safeLink} from './rich-text.js';

export function renderLibrary(parent,result,{onSearch,busy=false}={}){
 const doc=parent.ownerDocument;
 const add=(tag,text,container=parent,cls='')=>{const node=doc.createElement(tag);node.textContent=text;node.className=cls;container.append(node);return node;};
 if(!result)return;
 if(result.retrieval_version===4){renderUnifiedLibrary(parent,result,{onSearch,busy});return;}
 if(result.retrieval_version!==3){add('p','资料版本已更新，重新进入图书馆或点击下方按钮，获取当前项目的资料与 arXiv 论文。');return;}
 const context=add('details','',parent,'context-drawer');context.dataset.detail='library-query';add('summary','查看本次检索依据',context);add('p','检索依据：'+result.query,context);
 const section=(title,kicker,count)=>{const s=add('section','',parent,'resource-section');add('div',kicker,s,'section-kicker');const heading=add('div','',s,'section-heading');add('h3',title,heading);add('span',count+' 条',heading,'count-badge');return s;};
 const local=section('本地资料','01 / 建立基础',result.documents?.length||0);
 add('p',result.notice,local,'section-note');
 function cards(container,items,papers=false){const grid=add('div','',container,'resource-grid');for(const item of items??[]){
  const card=add('article','',grid,'knowledge-node');
  const meta=add('div','',card,'resource-meta');add('span',papers?'ARXIV · 论文':item.type==='tool'?'工具与文档':'阅读资料',meta,'resource-type');if(papers&&item.year)add('span',item.year,meta);
  const heading=add('h4','',card);const url=safeLink(item.url);const title=add(url?'a':'span','',heading);renderRichText(title,item.title||'未命名资料',{inline:true});
  if(url){title.href=url;title.target='_blank';title.rel='noopener noreferrer';}
  if(papers&&item.authors?.length)add('p',item.authors.join('、'),card,'resource-authors');
  if(item.snippet)renderRichText(add('div','',card,'resource-excerpt'),item.snippet);
  if(url)add('span','阅读原文 ↗',card,'resource-link-hint');
 }}
 cards(local,result.documents);
 const status=result.arxiv_status,papers=result.arxiv_papers??[];
 const external=section('arXiv 相关论文','02 / 深入研究',status==='ok'?papers.length:0);
 if(onSearch){
  const form=add('form','',external,'paper-search');
  const label=add('label','论文检索词（英文，多个主题用逗号分隔）',form);label.htmlFor='paper-query';
  const row=add('div','',form,'search-row');
  const input=doc.createElement('input');input.id='paper-query';input.value=result.arxiv_query||'';input.placeholder='例如：TinyML, embedded machine learning';input.maxLength=200;input.required=true;input.disabled=busy;row.append(input);
  const button=add('button',busy?'检索中…':'检索论文 ↗',row,'primary');button.type='submit';button.disabled=busy;
  form.onsubmit=e=>{e.preventDefault();if(!busy&&input.value.trim())return onSearch(input.value.trim());};
 }else if(result.arxiv_query)add('p','论文检索词：'+result.arxiv_query,external,'section-note');
 const message=status==='ok'?(papers.length?`找到 ${papers.length} 篇论文 · 下方为摘要节选`:'本次 arXiv 检索没有命中。可以调整英文关键词后重试。'):
  status==='failed'?'arXiv 暂时无法连接或响应异常。本地资料仍可查看，请稍后重试。':
  status==='disabled'?'arXiv 检索尚未启用，请检查后端配置。':
  status==='mock'?'当前为演示模式，未执行联网论文检索。':
  status==='needs_query'?'这个主题暂不能自动转换成论文检索词，请在上方填写英文主题后检索。':'尚未检索 arXiv，请点击下方按钮重新检索。';
 const state=add('p',message,external,'search-status');state.setAttribute('role','status');state.dataset.arxivStatus=status||'pending';
 if(status==='ok')cards(external,papers,true);
 const notes=add('details','',parent,'context-drawer');notes.dataset.detail='library-scope';add('summary','资料范围与使用说明',notes);add('p','目前覆盖本地资料与 arXiv 论文，暂不搜索网页教程。论文适合了解研究背景，不代表入门教程；目前尚未自动用于 Professor 回答。',notes);
}

function renderUnifiedLibrary(parent,result,{onSearch,busy}){
 const doc=parent.ownerDocument;
 const add=(tag,text,host=parent,cls='')=>{const n=doc.createElement(tag);n.textContent=text;n.className=cls;host.append(n);return n;};
 const labels={local:'本地资料',arxiv:'arXiv 论文',web:'网页搜索',resource:'课程与书籍'};
 const statuses={ok:'已检索',failed:'暂不可用',disabled:'未启用',mock:'演示模式',needs_query:'需要检索词',partial:'部分可用'};
 const sources=add('section','',parent,'search-sources');add('div','LIBRARY / DISCOVER',sources,'section-kicker');add('h3','为这个项目找到的资料',sources);
 for(const [source,label] of Object.entries(labels)){const status=result.sources?.[source]||'pending';const node=add('span',label+' · '+(statuses[status]||'尚未检索'),sources,'source-status');node.dataset.source=source;node.dataset.status=status;}
 add('p',result.notice||'',sources,'section-note');
 const items=(result.results||[]).filter(item=>{const source=['course','video','book'].includes(item.source)?'resource':item.source;return !['failed','disabled','mock'].includes(result.sources?.[source]);});
 const section=add('section','',parent,'resource-section');add('h3',`项目资料 · ${items.length} 条`,section);const grid=add('div','',section,'resource-grid');
 const types={paper:'论文',article:'文章',doc:'文档',tool:'工具',webpage:'网页',course:'课程',video:'视频',book:'书籍',resource:'学习资源'};
 for(const item of items){const card=add('article','',grid,'knowledge-node'),meta=add('div','',card,'resource-meta');add('span',(labels[item.source]||types[item.source]||'学习资源')+' · '+(types[item.type]||'资料'),meta,'resource-type');if(item.year)add('span',String(item.year),meta);
 const title=add('h4','',card),url=safeLink(item.url),link=add(url?'a':'span','',title);renderRichText(link,item.title||'未命名资料',{inline:true});if(url){link.href=url;link.target='_blank';link.rel='noopener noreferrer';}
 if(item.authors?.length)add('p',item.authors.join('、'),card,'resource-authors');if(item.snippet)renderRichText(add('div','',card,'resource-excerpt'),item.snippet);
 }
 if(!items.length)add('p','本次没有可显示的资料。可以重新检索，或调整下方论文关键词。',section,'search-status');
 const detail=add('details','',parent,'context-drawer');detail.dataset.detail='library-query';add('summary','检索依据与论文关键词',detail);add('p','检索依据：'+result.query,detail);
 if(onSearch){const form=add('form','',detail,'paper-search'),label=add('label','论文检索词（英文）',form);label.htmlFor='paper-query';const row=add('div','',form,'search-row'),input=add('input','',row);input.id='paper-query';input.value=result.arxiv_query||'';input.maxLength=200;input.required=true;input.disabled=busy;const button=add('button',busy?'检索中…':'更新检索 ↗',row,'primary');button.type='submit';button.disabled=busy;form.onsubmit=e=>{e.preventDefault();if(!busy&&input.value.trim())return onSearch(input.value.trim());};}
 add('p','资料来自本地库、arXiv、网页搜索和课程／书籍推荐；各来源独立显示检索状态。请打开原始链接确认内容与项目的适用性。',parent,'section-note');
}
