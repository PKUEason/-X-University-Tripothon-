import * as THREE from 'three';
import {GLTFLoader} from '../vendor/GLTFLoader.js';
import {identityFor} from './identity.js';

let assetPromise;
export function loadCharacterAsset() {
  if (!assetPromise) assetPromise = new GLTFLoader().loadAsync('./assets/student-rigged.glb').catch(error => {
    assetPromise = null;
    throw error;
  });
  return assetPromise;
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
        const m=original.clone();
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
  for(const name of ['Idle','Walk','Run']){
    const clip=THREE.AnimationClip.findByName(asset.animations,name);
    if(!clip)throw new Error(`Character is missing ${name}`);
    actions.set(name,mixer.clipAction(clip));
  }
  let current=actions.get('Idle'),motion='Idle',disposed=false,transitionRemaining=0;
  current.play();root.userData.motion=motion;
  return {root,update(dt,moving,running,reduceMotion=false,movementSpeed){
    if(disposed)return;
    const next=moving?(running?'Run':'Walk'):'Idle';
    if(next!==motion){const action=actions.get(next);action.reset().play();current.crossFadeTo(action,.18,false);current=action;motion=next;root.userData.motion=motion;transitionRemaining=.18;}
    // Freeze idle breathing when reduced motion is enabled, while preserving gait.
    const step=Math.min(Math.max(dt,0),.1);
    // The fitted legs travel 0.29 m / (20/60 s) in Walk and
    // 0.3625 m / (16/60 s) in Run. Match cadence to world displacement.
    current.setEffectiveTimeScale(moving&&Number.isFinite(movementSpeed)?Math.max(0,movementSpeed)/(running?1.359375:.87):1);
    mixer.update(reduceMotion&&!moving?Math.min(step,transitionRemaining):step);
    transitionRemaining=Math.max(0,transitionRemaining-step);
  },dispose(){
    disposed=true;mixer.stopAllAction();mixer.uncacheRoot(model);
    model.traverse(o=>{if(o.isSkinnedMesh)o.skeleton.dispose();});
    for(const m of materials.values())m.dispose();
    // Geometry/textures belong to the shared cached GLB and remain reusable.
  }};
}
