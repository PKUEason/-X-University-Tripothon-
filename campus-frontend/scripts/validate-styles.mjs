import {transform} from 'esbuild';

// esbuild recovers from some invalid CSS with warnings. Treat those as failures
// so a script accidentally saved over the stylesheet cannot ship unnoticed.
export async function validateStyles(css){
 const result=await transform(css,{loader:'css',sourcefile:'style.css',logLevel:'silent'});
 if(result.warnings.length)throw new Error('Invalid style.css: '+result.warnings.map(w=>w.text).join('; '));
 if(!css.trim())throw new Error('style.css is empty');
 return result;
}
