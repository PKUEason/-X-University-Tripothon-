import {build} from 'esbuild';
import {cp,mkdir,rm,readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {validateStyles} from './scripts/validate-styles.mjs';
await validateStyles(await readFile(new URL('./style.css',import.meta.url),'utf8'));
await validateStyles(await readFile(new URL('./glass.css',import.meta.url),'utf8'));
await build({entryPoints:[fileURLToPath(new URL('./node_modules/marked/lib/marked.esm.js',import.meta.url))],outfile:fileURLToPath(new URL('./src/markdown-vendor.js',import.meta.url)),bundle:true,format:'esm',platform:'browser',target:'es2022'});
await build({entryPoints:[fileURLToPath(new URL('../ai-backend/frontend/xuni-client/client.ts',import.meta.url))],outfile:fileURLToPath(new URL('./src/sdk.js',import.meta.url)),bundle:true,format:'esm',platform:'browser',target:'es2022'});
if(!process.argv.includes('--sdk')){
 // Validate the full browser module graph, including files served from public/.
 await build({entryPoints:[fileURLToPath(new URL('./src/app.js',import.meta.url))],bundle:true,write:false,platform:'browser',format:'esm',alias:{three:fileURLToPath(new URL('./public/vendor/three.module.js',import.meta.url))},plugins:[{name:'public-vendor',setup(b){b.onResolve({filter:/^\.\.\/vendor\//},args=>({path:fileURLToPath(new URL('./public/vendor/'+args.path.split('/').at(-1),import.meta.url))}));}}]});
 await rm(fileURLToPath(new URL('./dist',import.meta.url)),{recursive:true,force:true});
 await mkdir(fileURLToPath(new URL('./dist',import.meta.url)));
 for(const name of ['index.html','style.css','glass.css','src'])await cp(new URL('./'+name,import.meta.url),new URL('./dist/'+name,import.meta.url),{recursive:true});
 await cp(new URL('./public/',import.meta.url),new URL('./dist/',import.meta.url),{recursive:true});
 console.log('Built campus-frontend/dist; serve with the API proxy, not a static-only host.');
}
