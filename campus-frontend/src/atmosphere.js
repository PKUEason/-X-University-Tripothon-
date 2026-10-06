import * as THREE from "three";
export function createAtmosphere(scene, renderer) {
  const skyUniforms = { night: { value: 0 } };
  const sky = new THREE.Mesh(new THREE.SphereGeometry(260, 40, 24), new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false, uniforms: skyUniforms, vertexShader: "varying vec3 p;void main(){p=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}", fragmentShader: `varying vec3 p;uniform float night;void main(){vec3 d=normalize(p);float h=clamp(d.y*.8+.12,0.,1.);vec3 day=mix(vec3(.045,.31,.68),vec3(.008,.085,.34),pow(h,.7));vec3 dusk=mix(vec3(.012,.025,.06),vec3(.0005,.001,.01),h);float n=fract(sin(dot(floor(d.xz*650./max(.2,d.y)),vec2(12.9898,78.233)))*43758.5453);vec3 c=mix(day,dusk,night)+vec3(step(.9985,n)*night*.7*smoothstep(.0,.2,d.y));gl_FragColor=vec4(c,1.);#include <colorspace_fragment>}`.replace(";#include", ";\n#include") }));
  sky.frustumCulled = false;
  scene.add(sky);
  if (renderer.isWebGLRenderer) {
    const env = new THREE.Scene();
    env.background = new THREE.Color("#718ba9");
    const emit = (color, intensity, x, y, z, sx, sy, sz) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), new THREE.MeshBasicMaterial({ color }));
      m.material.color.multiplyScalar(intensity);
      m.position.set(x, y, z);
      env.add(m);
    };
    emit("#ffffff", 2.2, -10, 14, 5, 12, 2, 10);
    emit("#5dbdff", 1.6, 10, 4, -10, 3, 14, 12);
    emit("#efadfa", 1.2, -14, 3, -10, 3, 10, 6);
    const generator = new THREE.PMREMGenerator(renderer);
    const target2 = generator.fromScene(env, 0.04);
    scene.environment = target2.texture;
    generator.dispose();
    env.traverse((o) => {
      o.geometry?.dispose();
      o.material?.dispose();
    });
  }
  let target, quad, post, postCamera, bloomA, bloomB, extract, blur, composite;
  if (renderer.setRenderTarget) {
    target = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, depthBuffer: true });
    post = new THREE.Scene();
    postCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    bloomA = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, depthBuffer: false });
    bloomB = bloomA.clone();
    const shader = (uniforms, fragmentShader) => new THREE.ShaderMaterial({
      depthTest: false, depthWrite: false, uniforms,
      vertexShader: "varying vec2 v;void main(){v=uv;gl_Position=vec4(position.xy,0.,1.);}", fragmentShader
    });
    // Only glow is downsampled. Text, architecture and the final image retain full resolution.
    extract = shader({ source: { value: target.texture } }, `uniform sampler2D source;varying vec2 v;
      void main(){vec3 c=texture2D(source,v).rgb;float lum=max(c.r,max(c.g,c.b));gl_FragColor=vec4(c*max(0.,lum-1.)/(lum+.001),1.);}`);
    blur = shader({ source: { value: bloomA.texture }, stepSize: { value: new THREE.Vector2() } }, `uniform sampler2D source;uniform vec2 stepSize;varying vec2 v;
      void main(){vec3 c=texture2D(source,v).rgb*.227027;
      c+=(texture2D(source,v+stepSize*1.384615).rgb+texture2D(source,v-stepSize*1.384615).rgb)*.316216;
      c+=(texture2D(source,v+stepSize*3.230769).rgb+texture2D(source,v-stepSize*3.230769).rgb)*.070270;
      gl_FragColor=vec4(c,1.);}`);
    composite = shader({ source: { value: target.texture }, glow: { value: bloomA.texture }, strength: { value: .35 } }, `uniform sampler2D source;uniform sampler2D glow;uniform float strength;varying vec2 v;
      void main(){gl_FragColor=vec4(texture2D(source,v).rgb+texture2D(glow,v).rgb*strength,1.);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
      }`);
    quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), composite);
    quad.frustumCulled = false;
    post.add(quad);
  }
  let enabled = true;
  return { setNight(n) {
    skyUniforms.night.value = n ? 1 : 0;
    if (composite) composite.uniforms.strength.value = n ? .65 : .35;
  }, configure(settings) {
    enabled = settings.quality !== "performance";
    if (target) {
      const size = renderer.getDrawingBufferSize(new THREE.Vector2());
      target.setSize(size.x, size.y);
      bloomA.setSize(Math.max(1, Math.round(size.x / 4)), Math.max(1, Math.round(size.y / 4)));
      bloomB.setSize(bloomA.width, bloomA.height);
    }
  }, render(camera) {
    sky.position.copy(camera.position);
    if (!target || !enabled) {
      renderer.render(scene, camera);
      return renderer.info.render.calls;
    }
    renderer.setRenderTarget(target);
    renderer.render(scene, camera);
    const calls = renderer.info.render.calls;
    quad.material = extract;
    renderer.setRenderTarget(bloomA);
    renderer.render(post, postCamera);
    quad.material = blur;
    blur.uniforms.source.value = bloomA.texture;
    blur.uniforms.stepSize.value.set(1 / bloomA.width, 0);
    renderer.setRenderTarget(bloomB);
    renderer.render(post, postCamera);
    blur.uniforms.source.value = bloomB.texture;
    blur.uniforms.stepSize.value.set(0, 1 / bloomA.height);
    renderer.setRenderTarget(bloomA);
    renderer.render(post, postCamera);
    quad.material = composite;
    renderer.setRenderTarget(null);
    renderer.render(post, postCamera);
    return calls + 4;
  } };
}
