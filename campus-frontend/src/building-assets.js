import * as THREE from 'three';
import {GLTFLoader} from '../vendor/GLTFLoader.js';
export const authoredBuildings=[
 {id:'office-shell',space:'office',asset:'professor-refined.glb',position:[-15,0,0]},
 {id:'lab-shell',space:'lab',asset:'lab-refined.glb',position:[15,0,0]},
 {id:'gate-shell',space:'gate',asset:'gate-refined.glb',position:[0,0,12]}
];
export async function installBuildings(scene,slots,onStatus=()=>{},loader=new GLTFLoader()) {
 return Promise.all(authoredBuildings.map(async spec=>{
  onStatus('loading',spec.space);
  try {
   const {scene:model}=await loader.loadAsync('./assets/'+spec.asset);
   model.name=spec.space+' · Blender architectural asset';model.position.fromArray(spec.position);
   model.traverse(o=>{if(!o.isMesh)return;o.castShadow=o.receiveShadow=true;
    for(const m of Array.isArray(o.material)?o.material:[o.material]){
     if(m.name.startsWith('Glazing')){m.side=THREE.DoubleSide;m.depthWrite=false;m.envMapIntensity=1.3;o.castShadow=false;o.renderOrder=2;}
     if(m.name.startsWith('Light')||m.name.startsWith('Floor'))o.castShadow=false;
    }
   });
   // One soft local light per hall; geometry is batched by material for bounded draw calls.
   if(spec.space!=='gate'){const light=new THREE.PointLight('#ffe0ae',22,10,2);light.position.set(0,4.3,0);model.add(light);}
   scene.add(model);const previous=slots.get(spec.id);if(previous)previous.visible=false;slots.set(spec.id,model);
   onStatus('ready',spec.space);return model;
  }catch(error){onStatus('error',spec.space);return null;}
 }));
}
