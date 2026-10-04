export const SETTINGS_KEY='xuni-campus-settings-v1';
export const defaults={quality:'balanced',sensitivity:1,reduceMotion:false};
export function normalizeSettings(value={}){return {quality:['performance','balanced','high'].includes(value.quality)?value.quality:'balanced',sensitivity:Number.isFinite(Number(value.sensitivity))?Math.max(.5,Math.min(2,Number(value.sensitivity))):1,reduceMotion:value.reduceMotion===true};}
export function createSettingsUI({document,storage,apply,resetCamera}){
 let value;try{value=normalizeSettings(JSON.parse(storage.getItem(SETTINGS_KEY)||'{}'));}catch{value={...defaults};}
 const $=s=>document.querySelector(s);
 function render(){$('#quality').value=value.quality;$('#camera-sensitivity').value=String(value.sensitivity);$('#sensitivity-value').textContent=value.sensitivity.toFixed(1)+'×';$('#reduce-motion').checked=value.reduceMotion;}
 function save(){value=normalizeSettings({quality:$('#quality').value,sensitivity:$('#camera-sensitivity').value,reduceMotion:$('#reduce-motion').checked});storage.setItem(SETTINGS_KEY,JSON.stringify(value));render();apply(value);}
 $('#quality').onchange=save;$('#camera-sensitivity').oninput=save;$('#reduce-motion').onchange=save;
 $('#reset-camera').onclick=resetCamera;$('#reset-preferences').onclick=()=>{value={...defaults};render();save();};render();
 return {get value(){return value;}};
}
