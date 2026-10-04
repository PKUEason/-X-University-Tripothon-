import {spawn,execFileSync} from 'node:child_process';
import {openSync,closeSync} from 'node:fs';
import {mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import net from 'node:net';
const root=fileURLToPath(new URL('../',import.meta.url));
const local=root+'.local/',pidFile=local+'server.pid',logFile=local+'server.log';
const command=process.argv[2]??'start';
async function running(){try{const pid=Number(await readFile(pidFile,'utf8'));if(!Number.isSafeInteger(pid)||pid<2)return null;process.kill(pid,0);const command=execFileSync('/bin/ps',['-p',String(pid),'-o','command='],{encoding:'utf8'}).trim();return command.endsWith(root+'scripts/dev.mjs')?pid:null;}catch{return null;}}
const available=port=>new Promise(resolve=>{const server=net.createServer();server.once('error',()=>resolve(false));server.listen(port,'127.0.0.1',()=>server.close(()=>resolve(true)));});
async function healthy(){try{const response=await fetch('http://127.0.0.1:4176/health',{signal:AbortSignal.timeout(2000)});return response.ok&&(await response.json()).status==='ok';}catch{return false;}}
const pid=await running();
if(command==='status'){
 console.log(JSON.stringify({pid,healthy:await healthy(),url:'http://127.0.0.1:4176/',log:logFile}));
}else if(command==='stop'){
 if(pid){process.kill(pid,'SIGTERM');console.log('已请求停止校园前后端。');}else console.log('未找到后台进程。');
 await rm(pidFile,{force:true});
}else if(command==='start'){
 if(pid){console.log(await healthy()?'校园已在后台运行：http://127.0.0.1:4176/':'后台进程存在，但服务未就绪；请查看 '+logFile);process.exitCode=await healthy()?0:1;}
 else if(!(await available(4176))||!(await available(8000))){console.error('4176 或 8000 端口已被占用，未启动额外进程。');process.exitCode=1;}
 else{
  await mkdir(local,{recursive:true});
  const fd=openSync(logFile,'a',0o600);
  const child=spawn(process.execPath,[root+'scripts/dev.mjs'],{cwd:root,detached:true,stdio:['ignore',fd,fd],env:{...process.env,CAMPUS_PORT:'4176'}});
  closeSync(fd);
  await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});
  await writeFile(pidFile,String(child.pid),{mode:0o600});child.unref();
  let ok=false;
  for(let i=0;i<20;i++){if(await healthy()){ok=true;break;}await new Promise(resolve=>setTimeout(resolve,500));}
  console.log(ok?'校园已在后台启动：http://127.0.0.1:4176/':'启动尚未就绪，请查看 '+logFile);if(!ok)process.exitCode=1;
 }
}else{console.error('使用 start、stop 或 status。');process.exitCode=1;}
