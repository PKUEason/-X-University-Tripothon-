import * as THREE from "three";
import { mergeGeometries } from "../vendor/BufferGeometryUtils.js";
export function buildNeonCampus(scene) {
  let batches = new Map(), layer = scene;
  const animated = [], slots = new Map();
  const material = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.38, metalness: 0.22, ...extra });
  const pearl = material("#e4edff"), metal = material("#667993", { metalness: 0.7, roughness: 0.28 }), dark = material("#142e53"), glass = material("#288bc1", { metalness: 0.62, roughness: 0.16 }), floor = material("#abbad4", { metalness: 0.35, roughness: 0.32 });
  const neon = (color) => material(color, { emissive: color, emissiveIntensity: 4.2, roughness: 0.25 });
  const cyan = neon("#26daff"), pink = neon("#ff78ce"), violet = neon("#947aff"), warm = neon("#ffd59f");
  const panelColors = [cyan, pink, violet, warm];
  const bookColors = ["#79c9e5", "#c197cc", "#8999db", "#e4bc86"].map((c) => material(c, { roughness: 0.75, metalness: 0 }));
  function shape(g, m, x = 0, y = 0, z = 0) {
    g.translate(x, y, z);
    if (!batches.has(m)) batches.set(m, []);
    batches.get(m).push(g);
  }
  function box(x, y, z, w, h, d, m = pearl) {
    shape(new THREE.BoxGeometry(w, h, d), m, x, y, z);
  }
  function cylinder(x, y, z, r, h, m = pearl, rt = r, n = 48) {
    shape(new THREE.CylinderGeometry(rt, r, h, n), m, x, y, z);
  }
  function ring(x, y, z, r, m, t = 0.055) {
    const g = new THREE.TorusGeometry(r, t, 8, 80);
    g.rotateX(Math.PI / 2);
    shape(g, m, x, y, z);
  }
  function line(points, m, r = 0.035) {
    shape(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p))), Math.max(8, points.length * 5), r, 5, false), m);
  }
  function frame(x, y, z, w, h, m, r = 0.45) {
    const pts = [];
    for (const [cx, cy, start] of [[w / 2 - r, h / 2 - r, 0], [-w / 2 + r, h / 2 - r, 90], [-w / 2 + r, -h / 2 + r, 180], [w / 2 - r, -h / 2 + r, 270]]) for (let i = 0; i <= 8; i++) {
      const a = (start + i / 8 * 90) * Math.PI / 180;
      pts.push([x + cx + Math.cos(a) * r, y + cy + Math.sin(a) * r, z]);
    }
    pts.push(pts[0]);
    line(pts, m, 0.065);
  }
  function label(title, sub, x, y, z, w, color = "#59e9ff", h = w / 3.8) {
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 320;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#101a38";
    ctx.fillRect(0, 0, 1024, 320);
    ctx.fillStyle = color;
    ctx.fillRect(24, 22, 5, 276);
    ctx.font = "700 94px sans-serif";
    ctx.textAlign = "center";
    ctx.fillStyle = "#f2f8ff";
    ctx.fillText(title, 512, 148);
    ctx.fillStyle = color;
    ctx.font = "500 28px sans-serif";
    ctx.fillText(sub, 512, 231);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshStandardMaterial({ map: texture, emissiveMap: texture, emissive: "#ffffff", emissiveIntensity: 0.75, roughness: 0.35 }));
    mesh.position.set(x, y, z);
    layer.add(mesh);
    return mesh;
  }
  // Each authored building has an independently replaceable loading fallback.
  const baseBatches = batches;
  function beginBuilding(id) { batches = new Map(); layer = new THREE.Group(); layer.name = id + ' fallback'; }
  function endBuilding(id) {
    for (const [mat, geos] of batches) {
      const mesh = new THREE.Mesh(mergeGeometries(geos), mat);
      mesh.castShadow = mesh.receiveShadow = true; layer.add(mesh);
      geos.forEach(g => g.dispose());
    }
    scene.add(layer); slots.set(id, layer); batches = baseBatches; layer = scene;
  }
  box(0, -1.05, -8, 49, 2.1, 62, floor);
  box(0, -2.25, -8, 46, 0.4, 59, metal);
  box(0, -2.85, -8, 39, 0.8, 52, dark);
  for (const z of [-38.98, 22.98]) {
    box(0, -0.45, z, 48, 0.09, 0.06, cyan);
    box(0, -1.1, z, 48, 0.04, 0.06, pink);
  }
  for (const x of [-24.48, 24.48]) box(x, -0.45, -8, 0.06, 0.09, 61.9, cyan);
  for (let x = -24; x <= 24; x += 3) box(x, 8e-3, -8, 0.014, 0.015, 60, pearl);
  for (let z = -38; z <= 22; z += 3) box(0, 9e-3, z, 48, 0.016, 0.014, pearl);
  box(0, 0.025, -7, 6, 0.03, 57, material("#dce9ff"));
  for (const x of [-3.15, 3.15]) box(x, 0.049, -7, 0.055, 0.025, 55, cyan);
  box(0, 0.033, 7.8, 40, 0.025, 3.6, material("#cbdaf2"));
  for (const z of [6.05, 9.55]) box(0, 0.055, z, 39, 0.025, 0.045, pink);
  beginBuilding('gate-shell');
  for (const x of [-5, 5]) {
    box(x, 3, 12, 2, 6, 2, metal);
    box(x, 3, 13.015, 1.35, 5.45, 0.035, dark);
    frame(x, 3, 13.06, 1.55, 5.55, x < 0 ? cyan : pink, 0.2);
    box(x, 6.3, 12, 2.3, 0.35, 2.3, pearl);
  }
  box(0, 6.2, 12, 12, 0.5, 1.9, pearl);
  box(0, 6.5, 12, 12, 0.07, 1.8, cyan);
  label("X UNIVERSITY", "A WORLD BUILT ON CURIOSITY", 0, 5.65, 13.06, 7.6, "#7cfcff", 1.55);
  endBuilding('gate-shell');
  function building(x, z, w, d, h, title, sub, accent) {
    box(x, (h + 6) / 2, z, w, h - 6, d, glass);
    for (const side of [-1, 1]) {
      box(x + side * w / 2, 3, z, 0.25, 6, d, glass);
      box(x + side * (w / 2 - 1.25), 3, z + d / 2, 2.5, 6, 0.2, glass);
    }
    box(x, 3, z - d / 2, w, 6, 0.2, glass);
    box(x, 5.8, z + d / 2, w, 0.4, 0.3, pearl);
    box(x, h + 0.25, z, w + 0.65, 0.5, d + 0.65, pearl);
    for (const sx of [-1, 1]) {
      for (const sz of [-1, 1]) box(x + sx * (w / 2 + 0.12), h / 2, z + sz * (d / 2 - 0.1), 0.45, h + 0.8, 0.45, pearl);
      box(x + sx * (w / 2 + 0.36), h / 2, z + d / 2 + 0.15, 0.06, h - 0.3, 0.09, accent);
    }
    for (let y = 3; y < h; y += 1.7) {
      box(x, y, z + d / 2 + 0.08, w, 0.13, 0.2, pearl);
      box(x, y, z - d / 2 - 0.08, w, 0.13, 0.2, metal);
      for (const sx of [-1, 1]) box(x + sx * (w / 2 + 0.025), y, z, 0.12, 0.13, d, metal);
    }
    for (let xx = -w / 2 + 0.7; xx < w / 2; xx += 1.25) {
      box(x + xx, h / 2, z + d / 2 + 0.13, 0.07, h - 0.5, 0.12, metal);
      box(x + xx, h / 2, z - d / 2 - 0.13, 0.07, h - 0.5, 0.12, metal);
    }
    for (const sx of [-1, 1]) {
      box(x + sx * (w / 2 + 0.015), (h + 6) / 2, z, 0.025, h - 6, d - 0.5, glass);
      for (let zz = -d / 2 + 0.7; zz < d / 2; zz += 1.2) box(x + sx * (w / 2 + 0.04), h / 2, z + zz, 0.08, h - 0.5, 0.065, metal);
      box(x + sx * (w / 2 + 0.07), h - 1, z, 0.085, 0.05, d - 0.7, accent);
    }
    for (let y = 3; y < h; y += 1.7) {
      box(x, y - 0.15, z + d / 2 + 0.22, w, 0.06, 0.48, metal);
    }
    box(x, h + 0.6, z, w * 0.86, 0.12, d * 0.86, dark);
    for (const sx of [-1, 1]) box(x + sx * (w / 2 - 0.2), h + 0.95, z, 0.04, 1.4, d, metal);
    for (const sz of [-1, 1]) box(x, h + 0.95, z + sz * (d / 2 - 0.2), w, 1.4, 0.04, glass);
    box(x, h + 1, z, w * 0.58, 1, d * 0.6, metal);
    box(x, h + 2.6, z, 0.07, 2.2, 0.07, pearl);
    frame(x, h / 2 + 0.2, z + d / 2 + 0.25, w + 0.9, h + 0.3, accent, 0.6);
    label(title, sub, x, h - 1.6, z + d / 2 + 0.3, w - 0.7);
  }
  beginBuilding('office-shell');
  building(-15, -0.8, 7.6, 9.5, 17, "PROFESSOR", "DISCUSS / DISCOVER / DEFINE", pink);
  frame(-15, 1.9, 4.22, 2.8, 3.8, cyan, 0.15);
  label("RESEARCH", "ASK A BETTER QUESTION", -15, 5.8, 4.28, 6.5, "#ffa4e6");
  const mural = document.createElement("canvas");
  mural.width = 512;
  mural.height = 512;
  const mc = mural.getContext("2d");
  mc.fillStyle = "#2b287b";
  mc.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 10; i++) {
    mc.fillStyle = ["#26d7f5", "#ef6abb", "#9777f8", "#eac959"][i % 4];
    mc.fillRect(i * 52, 80 + i % 3 * 60, 38, 250);
  }
  mc.fillStyle = "#ffffff";
  mc.font = "bold 72px sans-serif";
  mc.textAlign = "center";
  mc.fillText("IMAGINE", 256, 90);
  mc.font = "26px sans-serif";
  mc.fillText("WHAT COMES NEXT?", 256, 444);
  const mt = new THREE.CanvasTexture(mural);
  mt.colorSpace = THREE.SRGBColorSpace;
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(6.2, 6.2), new THREE.MeshStandardMaterial({ map: mt, emissiveMap: mt, emissive: "#ffffff", emissiveIntensity: 0.65 }));
  screen.position.set(-15, 10.4, 4.29);
  layer.add(screen);
  endBuilding('office-shell');
  beginBuilding('lab-shell');
  building(15, -0.6, 7.6, 9, 8.4, "X LAB", "MAKE THE NEXT THING", cyan);
  frame(15, 1.9, 4.12, 2.6, 3.8, pink, 0.15);
  cylinder(15, 8.9, -0.6, 3.1, 0.45, pearl);
  const sphere = new THREE.SphereGeometry(2.7, 48, 24);
  shape(sphere, metal, 15, 11.25, -0.6);
  for (const y of [10.55, 11.85]) ring(15, y, -0.6, Math.sqrt(2.7 ** 2 - (y - 11.25) ** 2) + 0.02, pink, 0.085);
  for (let i = 0; i < 8; i++) {
    const a = i / 8 * Math.PI * 2;
    line(Array.from({ length: 20 }, (_, j) => {
      const b = j / 19 * Math.PI;
      return [15 + 2.73 * Math.sin(b) * Math.cos(a), 11.25 + 2.73 * Math.cos(b), -0.6 + 2.73 * Math.sin(b) * Math.sin(a)];
    }), pearl, 0.025);
  }
  endBuilding('lab-shell');
  // Keep a complete fallback in its own slot while the authored GLB loads.
  const campusBatches = batches;
  const libraryFallback = new THREE.Group();
  libraryFallback.name = 'Library loading fallback';
  batches = new Map(); layer = libraryFallback;
  box(-10, 3, -25, 0.2, 6, 26, glass);
  box(10, 3, -25, 0.2, 6, 26, glass);
  box(0, 3, -38, 20, 6, 0.2, glass);
  for (const x of [-6.6, 6.6]) box(x, 3, -12, 6.8, 6, 0.2, glass);
  box(0, 6.2, -25, 20.7, 0.4, 26.6, pearl);
  frame(0, 2.2, -11.78, 4.7, 4.4, cyan, 0.25);
  for (const x of [-9.7, 9.7]) box(x, 3, -25, 0.45, 6, 26, pearl);
  for (let x = -9; x <= 9; x += 1.5) {
    if (Math.abs(x) > 2.5) box(x, 3, -11.88, 0.07, 5.8, 0.2, pearl);
  }
  for (const y of [1.1, 3.5, 5.7]) box(0, y, -11.8, 19.3, 0.055, 0.08, cyan);
  cylinder(0, 7, -25, 9.3, 1.1, pearl);
  cylinder(0, 13.8, -25, 8.7, 12.4, glass, 0.25, 64);
  for (let i = 0; i < 20; i++) {
    const a = i / 20 * Math.PI * 2;
    line([[Math.cos(a) * 8.74, 7.6, -25 + Math.sin(a) * 8.74], [Math.cos(a) * 0.26, 20, -25 + Math.sin(a) * 0.26]], pearl, 0.042);
  }
  for (let y = 8; y < 20; y += 1.5) {
    const r = 8.7 - (y - 7.6) * 8.45 / 12.4;
    ring(0, y, -25, r + 0.015, metal, 0.048);
  }
  cylinder(0, 22, -25, 2.4, 4, pearl, 0, 64);
  ring(0, 7.6, -25, 8.8, pink, 0.08);
  label("LIBPEDIA", "IDEAS BEGIN WITH A QUESTION", 0, 5.02, -11.62, 9, "#ecaaff", 1.9);
  for (const z of [-20, -27, -34]) {
    box(-6, 1.6, z, 5.2, 3.2, 0.8, dark);
    for (let y = 0.25; y < 3.3; y += 0.76) {
      box(-6, y, z + 0.61, 5.3, 0.08, 1, pearl);
      for (let i = 0; i < 22; i++) box(-8.3 + i * 0.215, y + 0.31, z + 0.65, 0.15, 0.46 + i % 3 * 0.08, 0.34, bookColors[i % 4]);
    }
    box(6, 0.9, z, 5.2, 0.14, 2, pearl);
    for (const x of [3.6, 8.4]) box(x, 0.45, z, 0.12, 0.9, 1.7, metal);
    box(5, 1.05, z, 0.7, 0.08, 0.9, cyan);
  }
  for (const z of [-17, -22, -29, -35]) {
    box(0, 5.8, z, 17, 0.12, 0.16, metal);
    box(0, 5.69, z, 12, 0.035, 0.055, cyan);
    for (const x of [4.2, 7.8]) {
      box(x, 0.48, z + 1.8, 0.7, 0.12, 0.7, metal);
      box(x, 0.25, z + 1.8, 0.1, 0.5, 0.1, metal);
      box(x, 0.85, z + 2.1, 0.7, 0.65, 0.1, glass);
    }
  }
  label("THE NEXT QUESTION", "READ / CONNECT / DISCOVER", 0, 3.3, -37.85, 8, "#69e6ff", 2.1);
  for (const x of [-9.84, 9.84]) {
    for (const z of [-19, -26, -33]) {
      box(x, 2.7, z, 0.03, 3.6, 4, metal);
      box(x + (x < 0 ? 0.025 : -0.025), 2.7, z, 0.025, 3.2, 3.6, glass);
    }
  }
  for (const [mat, geos] of batches) {
    const mesh = new THREE.Mesh(mergeGeometries(geos), mat);
    mesh.castShadow = mesh.receiveShadow = true;
    libraryFallback.add(mesh);
    geos.forEach(g => g.dispose());
  }
  scene.add(libraryFallback); slots.set('library-shell', libraryFallback);
  batches = campusBatches; layer = scene;
  cylinder(-6, 0.25, 0, 0.85, 0.5, pearl);
  const knot = new THREE.Mesh(new THREE.TorusKnotGeometry(0.65, 0.15, 100, 12), pink);
  knot.position.set(-6, 1.65, 0);
  scene.add(knot);
  animated.push({ mesh: knot, y: 1.65, kind: "sculpture" });
  for (const x of [-8, 8]) {
    box(x, 0.35, 3, 2, 0.6, 1, pearl);
    box(x, 0.68, 3, 1.9, 0.08, 0.9, cyan);
  }
  const foliage = material("#379caf");
  for (const x of [-8, 8]) for (const z of [16, 7, -8]) {
    cylinder(x, 0.3, z, 0.75, 0.6, pearl);
    cylinder(x, 1.4, z, 0.13, 2.5, metal);
    const g = new THREE.SphereGeometry(1, 24, 16);
    g.scale(1.05, 1.5, 1.05);
    shape(g, foliage, x, 3.3, z);
    ring(x, 0.62, z, 0.73, cyan, 0.028);
  }
  for (const x of [-22, 22]) for (const z of [-31, -18, -6, 9, 19]) {
    box(x, 0.28, z, 2.1, 0.5, 3.5, pearl);
    box(x, 0.61, z, 1.7, 0.16, 3.1, foliage);
    box(x, 2.3, z, 0.065, 3.7, 0.065, metal);
    box(x, 4.2, z, 1.4, 0.07, 0.16, cyan);
  }
  for (const r of [1.4, 1.65, 2.6]) ring(0, 0.07, 0, r, cyan, 0.025);
  for (let z = 14; z > -13; z -= 2) box(0, 0.061, z, 0.12, 0.025, 0.65, pink);
  for (const x of [-16, 16]) {
    const id = x < 0 ? 'office-shell' : 'lab-shell';
    batches = new Map(); layer = slots.get(id);
    box(x, 0.78, -2.7, 3, 0.13, 1.25, pearl);
    box(x, 1.3, -3.1, 1.1, 0.65, 0.06, dark);
    box(x, 1.3, -3.05, 0.98, 0.5, 0.02, cyan);
    for (const [mat, geos] of batches) { const mesh=new THREE.Mesh(mergeGeometries(geos),mat);layer.add(mesh);geos.forEach(g=>g.dispose()); }
    batches=baseBatches;layer=scene;
  }
    // Flush the final desk geometry into its owning fallback above.
  const cityGeo = new THREE.BoxGeometry(1, 1, 1), cityMat = material("#99b5d7", { roughness: 0.62 });
  const wc = document.createElement("canvas");
  wc.width = 128;
  wc.height = 256;
  const wctx = wc.getContext("2d");
  wctx.fillStyle = "#103960";
  wctx.fillRect(0, 0, 128, 256);
  for (let r = 0; r < 16; r++) for (let c = 0; c < 5; c++) {
    wctx.fillStyle = (r + c) % 6 === 0 ? "#89bcce" : "#33618a";
    wctx.fillRect(c * 25 + 2, r * 16 + 2, 22, 12);
  }
  wctx.fillStyle = "#ef92d3";
  wctx.fillRect(0, 211, 128, 2);
  const wm = new THREE.CanvasTexture(wc);
  wm.colorSpace = THREE.SRGBColorSpace;
  const cityWindows = material("#8cbff6", { map: wm, roughness: 0.36, metalness: 0.35 });
  const count = 180, city = new THREE.InstancedMesh(cityGeo, cityMat, count), windows = new THREE.InstancedMesh(cityGeo, cityWindows, count * 4), lights = new THREE.InstancedMesh(cityGeo, cyan, count), roofs = new THREE.InstancedMesh(cityGeo, metal, count);
  const dummy = new THREE.Object3D();
  let seed = 517;
  const random = () => {
    seed = seed * 1664525 + 1013904223 >>> 0;
    return seed / 4294967296;
  };
  for (let i = 0; i < count; i++) {
    const a = random() * Math.PI * 2, r = 54 + random() * 95, x = Math.cos(a) * r, z = -10 + Math.sin(a) * r, h = 5 + random() * 32, w = 2.5 + random() * 5, d = 2.5 + random() * 6;
    dummy.position.set(x, -23 + h / 2, z);
    dummy.scale.set(w, h, d);
    dummy.updateMatrix();
    city.setMatrixAt(i, dummy.matrix);
    dummy.position.z = z + d / 2 + 0.025;
    dummy.scale.set(w * 0.77, h * 0.83, 0.025);
    dummy.updateMatrix();
    windows.setMatrixAt(i * 4, dummy.matrix);
    dummy.position.z = z - d / 2 - 0.025;
    dummy.updateMatrix();
    windows.setMatrixAt(i * 4 + 1, dummy.matrix);
    for (const side of [-1, 1]) {
      dummy.position.set(x + side * (w / 2 + 0.025), -23 + h / 2, z);
      dummy.scale.set(0.025, h * 0.83, d * 0.77);
      dummy.updateMatrix();
      windows.setMatrixAt(i * 4 + (side === -1 ? 2 : 3), dummy.matrix);
    }
    dummy.position.set(x + w / 2 + 0.025, -23 + h / 2, z + d / 2 + 0.08);
    dummy.scale.set(0.07, h * 0.7, 0.09);
    dummy.updateMatrix();
    lights.setMatrixAt(i, dummy.matrix);
    dummy.position.set(x, -23 + h + 0.8, z);
    dummy.scale.set(w * 0.64, 1.6, d * 0.6);
    dummy.updateMatrix();
    roofs.setMatrixAt(i, dummy.matrix);
  }
  scene.add(city, windows, lights, roofs);
  for (let i = 0; i < 8; i++) {
    const a = i / 8 * Math.PI * 2, r = 45 + random() * 30, x = Math.cos(a) * r, z = -10 + Math.sin(a) * r, y = 3 + random() * 16;
    label(["CREATE", "EXPLORE", "HELLO, FUTURE", "X UNIVERSITY"][i % 4], ["STAY CURIOUS", "BUILD YOUR OWN PATH", "LEARNING WITHOUT LIMITS"][i % 3], x, y, z, 5 + random() * 5, i % 2 ? "#ff8be2" : "#5dedff");
  }
  for (let i = 0; i < 14; i++) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.6 + i % 3 * 0.3, 0.6 + i % 3 * 0.3, 0.6 + i % 3 * 0.3), panelColors[i % 4]);
    m.position.set((random() - 0.5) * 56, 14 + random() * 19, -15 + (random() - 0.5) * 45);
    m.rotation.set(random(), random(), 0.4);
    scene.add(m);
    animated.push({ mesh: m, y: m.position.y, kind: "cube" });
  }
  for (const [mat, geos] of batches) {
    const m = new THREE.Mesh(mergeGeometries(geos), mat);
    m.castShadow = true;
    m.receiveShadow = true;
    scene.add(m);
    geos.forEach((g) => g.dispose());
  }
  return { slots, update(time, reduced) {
    if (reduced) return;
    animated.forEach(({ mesh, y, kind }, i) => {
      mesh.position.y = y + Math.sin(time * 0.45 + i) * 0.18;
      mesh.rotation.y = time * (kind === "cube" ? 0.1 : 0.24);
    });
  } };
}
