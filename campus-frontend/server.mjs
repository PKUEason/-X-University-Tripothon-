import http from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Readable} from 'node:stream';
const root=path.dirname(fileURLToPath(import.meta.url));
// Load only local backend configuration; no credential is emitted or served.
try{process.loadEnvFile(path.join(root,'../ai-backend/.env'));}catch{}
const backend=process.env.XUNI_BACKEND_URL??'http://127.0.0.1:8000';
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.glb':'model/gltf-binary','.jpg':'image/jpeg','.svg':'image/svg+xml','.json':'application/json'};
const port=Number(process.env.CAMPUS_PORT??4176);
http.createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost');
  if(url.pathname.startsWith('/api/')||url.pathname==='/health'){
   if(!['GET','POST','DELETE'].includes(req.method)){res.writeHead(405).end();return;}
   // No arbitrary destinations or client-supplied credentials. Only this local app may send mutation requests.
   if(req.headers.origin&&!['http://127.0.0.1:'+port,'http://localhost:'+port].includes(req.headers.origin)){res.writeHead(403).end();return;}
   const headers={'Content-Type':'application/json'};if(process.env.API_TOKEN)headers['X-API-Token']=process.env.API_TOKEN;
   const controller=new AbortController();res.on('close',()=>{if(!res.writableEnded)controller.abort();});
   const body=req.method==='POST'?req:undefined;
   const upstream=await fetch(new URL(url.pathname+url.search,backend),{method:req.method,headers,body,duplex:'half',signal:controller.signal});
   res.writeHead(upstream.status,{'Content-Type':upstream.headers.get('content-type')??'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
   if(upstream.body){const stream=Readable.fromWeb(upstream.body);stream.on('error',()=>res.destroy());stream.pipe(res);}else res.end();
   return;
  }
  let p=decodeURIComponent(url.pathname);if(p==='/')p='/index.html';
  const allowed=p==='/index.html'||p==='/style.css'||/^\/src\/[a-zA-Z0-9-]+\.js$/.test(p)||p==='/credits.html'||/^\/(assets|vendor)\/[a-zA-Z0-9_.-]+$/.test(p);
  if(!allowed)throw Error('not found');
  const base=/^\/(assets|vendor)\//.test(p)||p==='/credits.html'?path.join(root,'public'):root;
  const file=path.resolve(base,'.'+p);if(!file.startsWith(base+path.sep)||!(await stat(file)).isFile())throw Error('not found');
  res.writeHead(200,{'Content-Type':types[path.extname(file)]??'application/octet-stream','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}).end(await readFile(file));
 }catch(error){if(res.headersSent){res.destroy();return;}res.writeHead(req.url.startsWith('/api/')||req.url==='/health'?502:404,{'Content-Type':'application/json'}).end(JSON.stringify({detail:'服务暂不可用，请检查后端连接并恢复进度。'}));}
}).listen(port,'127.0.0.1',()=>console.log('X University connected campus: http://127.0.0.1:'+port));
