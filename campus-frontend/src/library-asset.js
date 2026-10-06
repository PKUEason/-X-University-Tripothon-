import * as THREE from 'three';
import {GLTFLoader} from '../vendor/GLTFLoader.js';

// One exported architectural asset. The procedural shell is only a loading/error fallback.
export async function installLibrary(scene, slots, onStatus = () => {}, loader = new GLTFLoader()) {
  onStatus('loading');
  try {
    const {scene: model} = await loader.loadAsync('./assets/library-refined.glb');
    model.name = 'Libpedia · Blender architectural asset';
    model.position.set(0, 0, -25);
    model.traverse(o => {
      if (!o.isMesh) return;
      o.castShadow = true;
      o.receiveShadow = true;
      const materials = Array.isArray(o.material) ? o.material : [o.material];
      for (const m of materials) {
        if (m.name.startsWith('Glazing')) {
          // Thin glazing with a readable interior. Avoid a second expensive full-screen
          // transmission pass on mobile; reflections come from the campus environment.
          m.side = THREE.DoubleSide;
          m.depthWrite = false;
          m.envMapIntensity = 1.3;
          o.castShadow = false;
          o.renderOrder = 2;
        }
        if (m.name.startsWith('Light') || m.name.startsWith('Floor')) o.castShadow = false;
      }
    });
    // Local warm pools illuminate surfaces behind glass; emissive strips alone
    // do not light neighbouring objects in the raster renderer.
    for (const [x,y,z,power,reach] of [[0,4.8,7,18,11],[0,4.8,-1,18,11],[0,4.8,-9,18,11],[0,8.8,0,32,9],[0,14.3,0,24,7],[0,19.7,0,18,6]]) {
      const light=new THREE.PointLight('#ffe0ae',power,reach,2);
      light.position.set(x,y,z);
      model.add(light);
    }
    scene.add(model);
    const fallback = slots.get('library-shell');
    if (fallback) fallback.visible = false;
    slots.set('library-shell', model);
    onStatus('ready');
    return model;
  } catch (error) {
    onStatus('error');
    return null;
  }
}
