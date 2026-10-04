import * as THREE from 'three';

// Original adult-proportioned campus characters. One continuous hair surface;
// articulated knees/elbows and a bevelled fabric backpack, all local geometry.
export function createStudent(profile={gender:'male'}){
 const root=new THREE.Group();root.name='campus-student';const female=profile.gender==='female';
 const mat=(color,roughness=.8)=>new THREE.MeshStandardMaterial({color,roughness});
 const skin=mat('#c99172',.69),hair=mat('#231c1b',.86),strand=mat('#332721'),shirt=mat(female?'#bb735f':'#577a94'),rib=mat(female?'#a66050':'#45677e'),cream=mat('#eee8d8'),pants=mat('#343e4e'),bag=mat('#a7824f'),seam=mat('#745737'),sole=mat('#c9c9ba'),ink=mat('#302a29'),white=mat('#eee6db'),lips=mat('#a66c59');
 const mesh=(geometry,material,parent=root,name='')=>{const m=new THREE.Mesh(geometry,material);m.name=name;m.castShadow=true;m.receiveShadow=false;parent.add(m);return m;};
 function ellipsoid(parent,x,y,z,rx,ry,rz,material,name=''){const m=mesh(new THREE.SphereGeometry(1,24,16),material,parent,name);m.position.set(x,y,z);m.scale.set(rx,ry,rz);return m;}
 function tube(parent,points,r,material,name=''){return mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p))),20,r,6,false),material,parent,name);}
 function loft(parent,rings,material,name){const original=rings;const spline=new THREE.CatmullRomCurve3(rings.map(([y,rx,rz])=>new THREE.Vector3(rx,y,rz)));rings=spline.getPoints(Math.max(18,rings.length*6)).map(v=>{let index=0;while(index<original.length-2&&(original.at(-1)[0]>original[0][0]?v.y>original[index+1][0]:v.y<original[index+1][0]))index++;const a=original[index],b=original[index+1],t=THREE.MathUtils.clamp((v.y-a[0])/(b[0]-a[0]||1),0,1);return [v.y,Math.max(.001,v.x),Math.max(.001,v.z),THREE.MathUtils.lerp(a[3]||0,b[3]||0,t)];});const vertices=[],indices=[],n=40;for(const [y,rx,rz,cz=0] of rings)for(let i=0;i<=n;i++){const a=i/n*Math.PI*2;vertices.push(Math.cos(a)*rx,y,Math.sin(a)*rz+cz);}for(let j=0;j<rings.length-1;j++)for(let i=0;i<n;i++){const a=j*(n+1)+i,b=a+n+1;if(rings.at(-1)[0]>=rings[0][0])indices.push(a,b,a+1,b,b+1,a+1);else indices.push(a,a+1,b,b,a+1,b+1);}const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setIndex(indices);g.computeVertexNormals();return mesh(g,material,parent,name);}
 function roundedBox(parent,w,h,d,r,material,x,y,z,name){const shape=new THREE.Shape();const left=-w/2+r,right=w/2-r,bottom=-h/2+r,top=h/2-r;shape.moveTo(left,-h/2);shape.lineTo(right,-h/2);shape.quadraticCurveTo(w/2,-h/2,w/2,bottom);shape.lineTo(w/2,top);shape.quadraticCurveTo(w/2,h/2,right,h/2);shape.lineTo(left,h/2);shape.quadraticCurveTo(-w/2,h/2,-w/2,top);shape.lineTo(-w/2,bottom);shape.quadraticCurveTo(-w/2,-h/2,left,-h/2);const g=new THREE.ExtrudeGeometry(shape,{depth:d-2*r,bevelEnabled:true,bevelThickness:r,bevelSize:r*.45,bevelSegments:4,steps:1,curveSegments:8});g.translate(0,0,-(d-2*r)/2);const m=mesh(g,material,parent,name);m.position.set(x,y,z);return m;}
 const body=new THREE.Group();root.add(body);
 loft(body,[[.91,.13,.085],[.96,.15,.095],[1.09,female?.135:.155,.09],[1.27,.18,.105],[1.39,.215,.105],[1.43,.16,.085],[1.47,.065,.065]],shirt,'knit-sweater');
 loft(body,[[.91,.134,.088],[.95,.15,.1]],rib,'ribbed-hem');
 ellipsoid(body,0,.9,0,.145,.10,.095,pants,'trouser-hips');
 const neck=mesh(new THREE.CylinderGeometry(.052,.062,.12,24),skin,body,'neck');neck.position.y=1.49;
 const collar=mesh(new THREE.TorusGeometry(.065,.012,8,32),cream,body,'shirt-collar');collar.rotation.x=Math.PI/2;collar.position.y=1.464;
 const head=new THREE.Group();head.position.set(0,1.655,-.008);body.add(head);
 loft(head,[[-.115,.025,.027,-.032],[-.097,.067,.055,-.015],[-.052,.091,.078,-.006],[0,.102,.09],[.044,.1,.088],[.086,.079,.07],[.12,.015,.014]],skin,'head-jaw-cheeks');
 for(const side of [-1,1]){
  ellipsoid(head,side*.102,-.012,.001,.017,.03,.013,skin,'ear');
  ellipsoid(head,side*.037,.006,-.083,.020,.0075,.007,white,'eye');ellipsoid(head,side*.037,.006,-.089,.005,.006,.0025,ink,'iris');
  tube(head,[[side*.018,.026,-.084],[side*.036,.029,-.087],[side*.06,.023,-.075]],.0035,hair,'eyebrow');
  tube(head,[[side*.018,.014,-.085],[side*.038,.015,-.090],[side*.058,.010,-.077]],.0018,skin,'upper-eyelid');
 }
 loft(head,[[.024,.006,.004,-.088],[-.014,.009,.013,-.09],[-.026,.013,.008,-.102],[-.035,.008,.006,-.093]],skin,'nose-bridge');
 tube(head,[[-.024,-.056,-.080],[-.009,-.058,-.086],[0,-.056,-.088],[.01,-.058,-.086],[.024,-.056,-.080]],.0028,lips,'lips');
 // A swept cap whose hairline wraps the forehead, temples and nape.
 const hairPoint=(a,t,offset=0)=>{const front=(1-Math.sin(a))/2,maxTheta=1.7-front*.44+front*.14*Math.cos(a+.6)+(female?.25*(1-front):0);const theta=t*maxTheta;const sweep=.007*Math.sin(a*2+.7)*Math.sin(theta);return [Math.cos(a)*(.11+offset)*Math.sin(theta),.008+(.13+offset)*Math.cos(theta)+sweep+.027*Math.exp(-Math.pow((theta-.65)/.5,2))*front*Math.sin(theta),Math.sin(a)*(.104+offset)*Math.sin(theta)+.003];};
 const v=[],ix=[],segments=72,rows=24;for(let j=0;j<=rows;j++)for(let i=0;i<=segments;i++)v.push(...hairPoint(i/segments*Math.PI*2,j/rows));for(let j=0;j<rows;j++)for(let i=0;i<segments;i++){const a=j*(segments+1)+i,b=a+segments+1;ix.push(a,a+1,b,a+1,b+1,b);}const hg=new THREE.BufferGeometry();hg.setAttribute('position',new THREE.Float32BufferAttribute(v,3));hg.setIndex(ix);hg.computeVertexNormals();mesh(hg,hair,head,'continuous-swept-hair');
 for(let i=0;i<15;i++){const a=i/15*Math.PI*2;const points=Array.from({length:12},(_,j)=>hairPoint(a+.7*(1-j/11),.18+j/11*.8,.001));tube(head,points,.0004,strand,'hair-strand');}
 if(female){
  loft(head,[[.04,.094,.065,.042],[-.035,.11,.078,.042],[-.13,.112,.066,.038],[-.22,.09,.042,.042]],hair,'sculpted-bob-back');
  for(const side of [-1,1])tube(head,[[side*.095,.03,.035],[side*.112,-.07,.04],[side*.096,-.19,.035]],.003,strand,'bob-edge');
 }
 // Padded rectangular canvas bag with seams, zipper, front pocket and grab handle.
 roundedBox(body,.305,.40,.17,.025,bag,0,1.19,.17,'backpack-body');
 roundedBox(body,.225,.145,.05,.014,rib,0,1.095,.275,'backpack-front-pocket');
 tube(body,[[-.113,1.15,.309],[0,1.16,.310],[.113,1.15,.309]],.004,cream,'pocket-zipper');
 tube(body,[[-.12,1.34,.272],[0,1.39,.273],[.12,1.34,.272]],.004,seam,'backpack-top-seam');
 tube(body,[[-.038,1.397,.17],[-.038,1.445,.17],[.038,1.445,.17],[.038,1.397,.17]],.012,seam,'backpack-handle');
 for(const side of [-1,1]){
  tube(body,[[side*.105,1.365,.16],[side*.157,1.448,.02],[side*.17,1.31,-.097],[side*.145,1.07,-.096],[side*.105,1.02,.14]],.018,bag,'padded-shoulder-strap');
  roundedBox(body,.035,.044,.016,.005,cream,side*.158,1.2,-.112,'strap-buckle');
 }
 const limbs=[];
 for(const side of [-1,1]){
  const arm=new THREE.Group();arm.position.set(side*.212,1.385,0);body.add(arm);arm.rotation.z=side*.055;ellipsoid(arm,0,0,0,.065,.075,.063,shirt,'rounded-shoulder');
  loft(arm,[[.01,.065,.063],[-.10,.058,.059],[-.245,.044,.047]],shirt,'upper-sleeve');
  const elbow=new THREE.Group();elbow.position.set(0,-.245,0);arm.add(elbow);
  ellipsoid(elbow,0,0,0,.043,.045,.045,shirt);loft(elbow,[[0,.043,.044],[-.20,.032,.036],[-.235,.030,.034]],shirt,'lower-sleeve');
  loft(elbow,[[-.217,.033,.037],[-.246,.031,.036]],rib,'sleeve-cuff');
  ellipsoid(elbow,0,-.292,-.003,.032,.052,.019,skin,'hand');
  for(let finger=0;finger<4;finger++){const x=(finger-1.5)*.013;tube(elbow,[[x,-.31,-.002],[x,-.346+Math.abs(finger-1.5)*.008,-.004]],.006,skin,'finger');}
  tube(elbow,[[side*-.027,-.28,-.001],[side*-.04,-.307,-.017]],.009,skin,'thumb');
  const leg=new THREE.Group();leg.position.set(side*.085,.89,0);root.add(leg);
  loft(leg,[[.02,.080,.082],[-.16,.07,.071],[-.40,.053,.054]],pants,'upper-trouser');
  const knee=new THREE.Group();knee.position.y=-.4;leg.add(knee);ellipsoid(knee,0,0,0,.053,.055,.053,pants);
  loft(knee,[[0,.052,.053],[-.23,.045,.047],[-.355,.037,.043]],pants,'lower-trouser');
  loft(knee,[[-.333,.039,.044],[-.36,.039,.044]],rib,'trouser-cuff');
  ellipsoid(knee,0,-.455,-.034,.055,.026,.117,sole,'sneaker-sole');
  ellipsoid(knee,0,-.414,-.034,.052,.045,.112,cream,'sneaker-upper');
  for(let lace=0;lace<3;lace++)tube(knee,[[-.028,-.372-lace*.003,-.012-lace*.02],[.028,-.372-lace*.003,-.012-lace*.02]],.003,sole,'shoelace');
  limbs.push({arm,elbow,leg,knee,side});
 }
 let phase=0,blend=0;
 return {root,update(dt,moving,running,reduceMotion=false){blend=THREE.MathUtils.damp(blend,moving?1:0,12,dt);phase+=dt*(running?10:6.8);const stride=(running?.62:.38)*blend;for(const {arm,elbow,leg,knee,side}of limbs){const wave=Math.sin(phase+(side<0?Math.PI:0));leg.rotation.x=wave*stride;knee.rotation.x=Math.max(0,-wave)*stride*.95;arm.rotation.x=-wave*stride*.7;elbow.rotation.x=-.13-Math.max(0,wave)*stride*.3;}body.position.y=reduceMotion?0:Math.sin(phase*2)*.008*blend;body.rotation.z=reduceMotion?0:Math.sin(phase)*.014*blend;},dispose(){const geos=new Set(),mats=new Set();root.traverse(o=>{if(o.isMesh){geos.add(o.geometry);mats.add(o.material);}});geos.forEach(g=>g.dispose());mats.forEach(m=>m.dispose());}};
}

export function createStudentPreview(container){
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(280,310);renderer.setClearColor(0,0);renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;container.append(renderer.domElement);renderer.domElement.setAttribute('aria-label','学生角色三维预览，可拖动查看书包');
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(32,280/310,.1,20);camera.position.set(1.7,1.5,-3.7);camera.lookAt(0,.95,0);scene.add(new THREE.HemisphereLight(0xf4f7ff,0x7c715d,2));const light=new THREE.DirectionalLight(0xffead4,2.5);light.position.set(-3,5,-4);scene.add(light);
 const base=new THREE.Mesh(new THREE.CylinderGeometry(.43,.46,.05,48),new THREE.MeshStandardMaterial({color:'#cdd9cf',roughness:1}));base.position.y=-.025;scene.add(base);
 let student=createStudent(),last=performance.now(),drag=false,previousX=0;scene.add(student.root);student.root.rotation.y=-.3;
 renderer.domElement.onpointerdown=e=>{drag=true;previousX=e.clientX;renderer.domElement.setPointerCapture(e.pointerId);};renderer.domElement.onpointermove=e=>{if(drag){student.root.rotation.y+=(e.clientX-previousX)*.015;previousX=e.clientX;}};renderer.domElement.onpointerup=renderer.domElement.onpointercancel=()=>drag=false;
 function frame(now){requestAnimationFrame(frame);const dt=Math.min((now-last)/1000,.05);last=now;if(!container.closest('dialog')?.open)return;student.update(dt,false,false);renderer.render(scene,camera);}requestAnimationFrame(frame);
 return {setProfile(profile){const angle=student.root.rotation.y;scene.remove(student.root);student.dispose();student=createStudent(profile);student.root.rotation.y=angle;scene.add(student.root);}};
}
