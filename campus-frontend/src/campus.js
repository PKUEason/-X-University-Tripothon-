// Metres, Y-up. Business IDs and traversal geometry survive art replacement.
export const spaces = {
 gate:{name:'X Gate',label:'提出一个目标',spawn:[0,16],hotspot:[0,14],radius:2.6},
 plaza:{name:'Plaza',label:'查看任务与下一站',spawn:[0,2],hotspot:[0,0],radius:2.5},
 library:{name:'Library',label:'建立知识地图',spawn:[0,-16],hotspot:[0,-19],radius:2.6},
 office:{name:'Professor Office',label:'与 Professor 研讨',spawn:[-15,1],hotspot:[-15,2],radius:2.6},
 lab:{name:'X Lab',label:'形成项目方案',spawn:[15,1],hotspot:[15,2],radius:2.6}
};
export const spaceAt = (x,z)=>Math.abs(x+15)<3.65&&z<4.7&&z>-4.65?'office':Math.abs(x-15)<3.65&&z<4.7&&z>-4.65?'lab':z < -12 && Math.abs(x) < 9.72 ? 'library' : z < 10 ? 'plaza' : 'gate';
export const collisionBoxes = [
 {x:-6,z:0,w:.85,d:.85,h:2.3},
 ...[-8,8].map(x=>({x,z:3,w:1,d:.5,h:1.2})),
 ...[-8,8].flatMap(x=>[16,7,-8].map(z=>({x,z,w:.75,d:.75,h:4.8}))),
 ...[-16,16].map(x=>({x,z:-2.7,w:1.5,d:.625,h:1.65})),
 {x:-5,z:12,w:1,d:1,h:6},{x:5,z:12,w:1,d:1,h:6},
 {x:-10,z:-25,w:.25,d:13,h:6},{x:10,z:-25,w:.25,d:13,h:6},{x:0,z:-38,w:10,d:.25,h:6},
 {x:-6.6,z:-12,w:3.4,d:.25,h:6},{x:6.6,z:-12,w:3.4,d:.25,h:6},
 ...[-17,-22,-29,-35].flatMap(z=>[4.2,7.8].map(x=>({x,z:z+1.8,w:.35,d:.4,h:1.2}))),
 ...[-20,-27,-34].flatMap(z=>[{x:-6,z,w:2.6,d:.7,h:3.2},{x:6,z,w:2.6,d:1,h:1}]),
 ...[-15,15].flatMap(x=>[{x:x-4,z:0,w:.2,d:5,h:7},{x:x+4,z:0,w:.2,d:5,h:7},{x,z:-5,w:4,d:.2,h:7},{x:x-2.8,z:5,w:1.2,d:.2,h:7},{x:x+2.8,z:5,w:1.2,d:.2,h:7}])
];
export function canWalk(x,z){return x>=-21&&x<=21&&z>=-37.4&&z<=20&&!collisionBoxes.some(c=>Math.abs(x-c.x)<c.w+.28&&Math.abs(z-c.z)<c.d+.28);}
// Visibility graph around expanded obstacle corners; routes start at the player.
export function segmentClear(a,b){
 if(!canWalk(...a)||!canWalk(...b))return false;
 const dx=b[0]-a[0],dz=b[1]-a[1];
 for(const c of collisionBoxes){
  let lo=0,hi=1;
  for(const [origin,delta,min,max] of [[a[0],dx,c.x-c.w-.285,c.x+c.w+.285],[a[1],dz,c.z-c.d-.285,c.z+c.d+.285]]){
   if(Math.abs(delta)<1e-10){if(origin<=min||origin>=max){lo=2;break;}}
   else{const t1=(min-origin)/delta,t2=(max-origin)/delta;lo=Math.max(lo,Math.min(t1,t2));hi=Math.min(hi,Math.max(t1,t2));}
  }
  if(lo<=hi)return false;
 }
 return true;
}
export function routeTo(position,target){
 if(!spaces[target])return [];
 const start=[position.x,position.z],end=spaces[target].spawn;
 if(Math.hypot(start[0]-end[0],start[1]-end[1])<.2)return [];
 if(segmentClear(start,end))return [[...end]];
 const corners=collisionBoxes.flatMap(c=>[-1,1].flatMap(x=>[-1,1].map(z=>[c.x+x*(c.w+.36),c.z+z*(c.d+.36)]))).filter(p=>canWalk(...p));
 const nodes=[start,end,...corners],distance=nodes.map(()=>Infinity),previous=nodes.map(()=>-1),visited=new Set();distance[0]=0;
 while(visited.size<nodes.length){
  let best=-1;for(let i=0;i<nodes.length;i++)if(!visited.has(i)&&(best<0||distance[i]<distance[best]))best=i;
  if(best<0||distance[best]===Infinity)break;if(best===1)break;visited.add(best);
  for(let i=1;i<nodes.length;i++){if(visited.has(i)||!segmentClear(nodes[best],nodes[i]))continue;const d=distance[best]+Math.hypot(nodes[best][0]-nodes[i][0],nodes[best][1]-nodes[i][1]);if(d<distance[i]){distance[i]=d;previous[i]=best;}}
 }
 if(!Number.isFinite(distance[1]))return [];
 const path=[];for(let i=1;i>0;i=previous[i]){if(i<0)return [];path.unshift(nodes[i]);}return path;
}
export const assetSlots = [
 {id:'gate-shell',spaceId:'gate',format:'glb',url:null,position:[0,0,12],rotationY:0,scale:1,placeholder:true},
 {id:'office-shell',spaceId:'office',format:'glb',url:null,position:[-15,0,0],rotationY:0,scale:1,placeholder:true},
 {id:'lab-shell',spaceId:'lab',format:'glb',url:null,position:[15,0,0],rotationY:0,scale:1,placeholder:true},
 {id:'library-shell',spaceId:'library',format:'glb',url:null,position:[0,0,-25],rotationY:0,scale:1,placeholder:true},
 {id:'plaza-landmark',spaceId:'plaza',format:'glb',url:null,position:[-7,0,3],rotationY:0,scale:1,placeholder:true}
];
