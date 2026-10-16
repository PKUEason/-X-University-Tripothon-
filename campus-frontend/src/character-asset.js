import * as THREE from 'three';
import {GLTFLoader} from '../vendor/GLTFLoader.js';
import {identityFor} from './identity.js';

const characterAssets={male:'student-male-zip.glb?v=fresh-native-20261015',female:'student-female.glb?v=a04d0240'};
const assetPromises=new Map();
export function loadCharacterAsset(gender='male') {
  const key=gender==='female'?'female':'male';
  if(!assetPromises.has(key))assetPromises.set(key,new GLTFLoader().loadAsync(`./assets/${characterAssets[key]}`).catch(error=>{
    assetPromises.delete(key);throw error;
  }));
  return assetPromises.get(key);
}

// Apply the requested softer reflections to the fresh ZIP import. The albedo
// correction happens before lighting, so directional light and night still work.
function cloneCharacterMaterial(original){
  if(original.name!=='tripo_mat_337953e8')return original.clone();
  const material=new THREE.MeshPhysicalMaterial();
  // Only copy the common fields; Physical.copy requires Physical-only vectors.
  THREE.MeshStandardMaterial.prototype.copy.call(material,original);
  material.defines={STANDARD:'',PHYSICAL:''};
  material.metalness=original.metalness*.15;
  material.envMapIntensity=.4;
  material.specularIntensity=.15;
  material.onBeforeCompile=shader=>{
    shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
      vec3 authoredColor=sRGBTransferOETF(vec4(max(diffuseColor.rgb,vec3(0.)),1.)).rgb;
      float authoredLuma=dot(authoredColor,vec3(.2126,.7152,.0722));
      authoredColor=clamp(mix(vec3(authoredLuma),authoredColor,1.3),0.,1.);
      diffuseColor.rgb=sRGBTransferEOTF(vec4(authoredColor,1.)).rgb*vec3(1.3,1.02,.83);
    `);
  };
  material.customProgramCacheKey=()=> 'designer-male-zip-soft-reflections-20261016';
  return material;
}

// A normal Object3D clone still points at the original skeleton's bones. Remap
// those references so campus and profile-preview characters animate independently.
export function instantiateCharacter(asset, role) {
  const model=asset.scene.clone(true), nodes=new Map();
  function pair(source,copy){nodes.set(source,copy);source.children.forEach((child,i)=>pair(child,copy.children[i]));}
  pair(asset.scene,model);
  const materials=new Map();
  asset.scene.traverse(source=>{
    const copy=nodes.get(source);
    if(source.isSkinnedMesh){
      copy.skeleton=source.skeleton.clone();
      copy.skeleton.bones=source.skeleton.bones.map(bone=>nodes.get(bone));
      copy.bind(copy.skeleton,source.bindMatrix);
      copy.frustumCulled=false; // Animated limbs can leave the rest-pose bounds.
    }
    if(!copy.isMesh)return;
    copy.castShadow=true;copy.receiveShadow=false;
    function material(original){
      if(!materials.has(original)){
        // Keep both supplied materials lit: an unlit material freezes the
        // texture's highlights even when the campus sun or character turns.
        const m=cloneCharacterMaterial(original);
        if(m.name==='IdentityAccent')m.color.set(identityFor(role).color);
        materials.set(original,m);
      }
      return materials.get(original);
    }
    copy.material=Array.isArray(source.material)?source.material.map(material):material(source.material);
  });
  model.rotation.y=Math.PI; // glTF front +Z -> campus movement forward -Z.
  const root=new THREE.Group();root.name='designer-explorer';root.add(model);
  const mixer=new THREE.AnimationMixer(model),actions=new Map();
  for(const name of ['Idle','Walk','Run'])if(!THREE.AnimationClip.findByName(asset.animations,name))throw new Error(`Character is missing ${name}`);
  for(const clip of asset.animations)actions.set(clip.name,mixer.clipAction(clip));
  let current=actions.get('Idle'),motion='Idle',disposed=false,transitionRemaining=0,gesture=null;
  const speeds=asset.scene.userData.locomotionSpeed??{Walk:.87,Run:3.2};
  function transition(next){if(next===motion)return;const action=actions.get(next);action.reset().play();current.crossFadeTo(action,.18,false);current=action;motion=next;root.userData.motion=motion;transitionRemaining=.18;}
  mixer.addEventListener('finished',event=>{if(event.action===current)gesture=null;});
  current.play();root.userData.motion=motion;
  return {root,availableMotions:[...actions.keys()],playMotion(name){
    if(!disposed&&name==='Idle'){gesture=null;transition('Idle');return true;}
    if(disposed||!['Greet','Clap','Dance'].includes(name)||!actions.has(name))return false;
    gesture=name;actions.get(name).setLoop(THREE.LoopOnce,1);actions.get(name).clampWhenFinished=true;
    // Restart a repeated request without fading an action into itself.
    if(motion===name)current.reset().play();else transition(name);return true;
  },update(dt,moving,running,reduceMotion=false,movementSpeed){
    if(disposed)return;
    if(moving)gesture=null;
    const next=moving?(running?'Run':'Walk'):(gesture||'Idle');
    transition(next);
    const step=Math.min(Math.max(dt,0),.1);
    current.setEffectiveTimeScale(moving&&Number.isFinite(movementSpeed)?Math.max(0,movementSpeed)/(speeds[next]||1):1);
    mixer.update(reduceMotion&&!moving&&!gesture?Math.min(step,transitionRemaining):step);
    transitionRemaining=Math.max(0,transitionRemaining-step);
  },dispose(){
    disposed=true;mixer.stopAllAction();mixer.uncacheRoot(model);
    model.traverse(o=>{if(o.isSkinnedMesh)o.skeleton.dispose();});
    for(const m of materials.values())m.dispose();
    // Geometry/textures belong to the shared cached GLB and remain reusable.
  }};
}
