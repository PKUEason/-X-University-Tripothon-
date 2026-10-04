import {spawn} from 'node:child_process';
import {access} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const backend=fileURLToPath(new URL('../../ai-backend/',import.meta.url));
const frontend=fileURLToPath(new URL('../',import.meta.url));
const python=backend+(process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
try{await access(python);}catch{console.error('请先按 README 创建 ai-backend/.venv 并安装依赖。');process.exit(1);}
const children=[];let stopping=false;
function stop(){if(stopping)return;stopping=true;for(const child of children)child.kill('SIGTERM');}
function start(command,args,cwd,env){const child=spawn(command,args,{cwd,env:{...process.env,...env},stdio:'inherit'});children.push(child);child.on('error',error=>{console.error(error.message);stop();});child.on('exit',()=>stop());}
process.on('SIGINT',stop);process.on('SIGTERM',stop);
start(python,['run.py'],backend,{HOST:'127.0.0.1',PORT:'8000',RELOAD:'false',DATA_DIR:'data/campus-integration'});
start(process.execPath,['server.mjs'],frontend,{XUNI_BACKEND_URL:'http://127.0.0.1:8000',CAMPUS_PORT:process.env.CAMPUS_PORT??'4176'});
