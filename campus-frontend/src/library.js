import {renderRichText,safeLink} from './rich-text.js';

export function renderLibrary(parent,result,{onSearch,busy=false}={}){
 const doc=parent.ownerDocument;
 const add=(tag,text,container=parent,cls='')=>{const node=doc.createElement(tag);node.textContent=text;node.className=cls;container.append(node);return node;};
 if(!result)return;
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
