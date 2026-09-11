'use strict';
module.exports=({round,field,mesh,C,hash,grain})=>{
 const f=field('kitchen-furniture',.05,'fixtures',0);
 function table(g,x,y,z,w,d){g.box(x,y+.87,z,w,.18,d,C.board);for(const a of[-1,1])for(const b of[-1,1])g.box(x+a*(w/2-.2),y+.4,z+b*(d/2-.18),.16,.85,.16,C.beam);}
 function bench(g,x,y,z,w){g.box(x,y+.48,z,w,.13,.37,C.wood);for(const s of[-1,1])g.box(x+s*(w/2-.2),y+.22,z,.13,.45,.3,C.beam);}
 function boxChest(g,x,y,z,w,d){g.box(x,y+.42,z,w,.8,d,C.wood);g.box(x,y+.84,z,w+.08,.12,d+.06,C.board);for(const s of[-1,1])g.box(x+s*w*.28,y+.43,z+d/2+.03,.055,.8,.05,C.iron);}
 // Wide low hearth, dry masonry hood and a true dark opening.
 f.box(-7.25,.18,-5.25,2.8,.36,2.35,11);for(const x of[-8.3,-6.2])f.box(x,1.1,-5.3,.55,2,1.8,10);f.box(-7.25,1.9,-5.3,2.65,.45,1.8,11);f.box(-7.25,1.02,-5.9,1.7,1.45,.25,C.dark);for(let i=0;i<5;i++)f.box(-7.8+i*.27,.55,-4.9,.2,.35+.07*(i%3),.5,34);f.fill([-8.55,2.1,-6.3,-5.95,3.7,-4.3],(x,y,z)=>Math.abs(x+7.25)<1.3-(y-2.1)*.3&&z< -4.5-(y-2.1)*.2,11);
 table(f,-4,0,1.65,4.1,1.6);bench(f,-4,0,.48,4.2);bench(f,-4,0,2.83,3.2);
 table(f,-7.5,0,-2.1,2.3,1.15);f.box(-7.35,1.04,-2.1,1.2,.2,.75,C.iron);f.box(-7.35,1.15,-2.1,1,.13,.58,29);
 f.box(-2,1.1,-4.8,.8,2.15,1.45,C.wood);for(const y of[.4,1,1.6,2.2])f.box(-1.53,y,-4.8,.25,.09,1.5,C.board);
 boxChest(f,-3.5,0,-6.6,2.4,.95);boxChest(f,-.7,0,-6.6,1.4,.85);f.box(-7.15,2.1,-2.5,2.2,.09,.09,C.beam);
 mesh(f);
 const workshop=field('edmund-bay',.05,'fixtures',0);table(workshop,7.25,-.15,5.35,4.25,1.3);workshop.box(8.4,1.03,5.6,.44,.35,.44,C.iron);workshop.beam([8.4,1.06,5.7],[8.4,1.06,6.05],.04,C.iron);boxChest(workshop,8.8,0,1.65,1.55,.9);
 workshop.box(4.1,1.7,4.8,.18,3.4,.18,C.beam);workshop.beam([4.1,3.3,4.8],[6.5,3.3,4.8],.11,C.beam);workshop.beam([4.1,2.25,4.8],[5.75,3.3,4.8],.075,C.wood);workshop.beam([6.3,3.25,4.8],[6.3,1.5,4.8],.03,C.iron);for(let i=0;i<5;i++)workshop.beam([5.1+i*.6,2.5,2.4],[5.1+i*.6,2.68,3.65],.055,C.lightwood);workshop.beam([4.8,2.58,3.1],[8,2.58,3.1],.1,C.wood);mesh(workshop);
 const sleep=field('sleeping',.05,'fixtures',1);
 function bed(x,z,w,d,c){sleep.box(x,4.09,z,w,.45,d,C.wood);sleep.box(x,4.38,z,w-.12,.24,d-.08,32);sleep.box(x,4.57,z+.25,w-.1,.18,d-.65,c);sleep.box(x,4.68,z-d/2+.34,w*.7,.17,.5,28);sleep.box(x,4.48,z-d/2,w+.07,1.1,.12,C.beam);}
 bed(-4.7,-4.25,2.25,2.5,25);bed(.1,-4.3,1.12,2.05,29);table(sleep,-4.8,3.8,2.6,1.65,.86);bench(sleep,-4.8,3.8,3.45,1.6);boxChest(sleep,-6.85,3.8,-.1,1.1,.65);mesh(sleep);
 const pipes=field('water-heat',.05,'facilities',0);
 // Cistern feet land directly on the basalt shoulder; bands and lid are distinct.
 pipes.box(-10.05,1.8,-9.1,2.4,.27,2.5,11);pipes.cylinder(-10.05,3.65,-9.1,.95,2.5,C.wood);for(const y of[2.46,3.15,4.65])pipes.cylinder(-10.05,y,-9.1,1,.1,C.iron,.1);pipes.cylinder(-10.05,4.97,-9.1,1.08,.17,C.board);for(const z of[-9.7,-8.5])pipes.box(-10.05,2.17,z,1.3,.5,.28,C.beam);
 function tube(points,r=.07,c=C.copper){for(let i=1;i<points.length;i++)pipes.beam(points[i-1],points[i],r,c);}
 tube([[-8.5,6.6,-7.45],[-8.5,5.4,-7.45],[-9.7,5.4,-7.45],[-9.7,5,-9.1]],.11);tube([[-10.05,2.8,-8.2],[-10.05,-.18,-8.2],[-7.35,-.18,-8.2],[-7.35,-.18,-2.6],[-7.35,1.6,-2.6],[-7.35,1.6,-2.1]],.065);
 tube([[-6.1,1.2,-5.3],[-5.75,1.2,-5.3],[-5.75,1.2,-3.2],[-8.8,1.2,-3.2],[-8.8,1.2,.3]],.08,16);for(let i=0;i<4;i++)tube([[-8.8,.7+i*.2,.3],[-7.9,.7+i*.2,.3]],.045,16);
 pipes.box(-8.55,1,.3,1.7,1.3,.2,11);pipes.cylinder(-5.8,1.7,-5.35,.26,.7,16);
 tube([[-8.8,.7,.3],[-8.8,1.3,.3]],.065,16);tube([[-7.9,1.3,.3],[-7.9,.7,.3],[-7.9,.7,-3.6],[-5.6,.7,-3.6],[-5.6,.7,-5.3],[-6.15,.7,-5.3]],.065,16);
 for(const[x,y,z]of[[-10.05,1.05,-8.2],[-5.75,1.3,-3.2],[-9.7,5.2,-8.28]]){pipes.ellipsoid(x,y,z,.15,.15,.15,C.brass);pipes.beam([x-.2,y+.1,z],[x+.2,y+.1,z],.035,C.iron);}
 mesh(pipes);
 const flue=field('chimney',.1,'roof',2);flue.box(-7.25,6.35,-5.55,.75,6.2,.75,11);flue.box(-7.25,9.5,-5.55,1.2,.2,1.2,C.iron);flue.box(-7.25,9.85,-5.55,.8,.4,.8,C.iron);flue.box(-7.25,10.1,-5.55,1.25,.18,1.25,C.iron);mesh(flue);
 const pier=field('pier-hardware',.05,'facilities',1);for(const x of[3.9,7.3]){pier.cylinder(x,4.02,6.75,.15,.4,C.iron);pier.beam([x-.25,4.17,6.75],[x+.25,4.17,6.75],.055,C.iron);}pier.box(7.75,5.1,5.25,.21,2.6,.21,C.wood);pier.beam([7.75,6.36,5.25],[6.2,6.36,5.25],.11,C.iron);pier.beam([7.75,5.6,5.25],[6.45,6.36,5.25],.065,C.wood);pier.beam([6.35,6.25,5.25],[6.35,4.15,5.25],.025,C.iron);pier.cylinder(7.55,4.12,5.5,.31,.4,C.wood);pier.beam([3.9,4.1,6.75],[5.2,4.35,7.35],.03,6);mesh(pier);
 require('./eyrie-miriam-deck.cjs')({field,mesh,C});
 if(round>=4){
 const join=field('craft-joints',.05,'details',0);
 for(const[x,z]of[[-8.8,1.8],[4.9,1.8],[9.7,6.9],[3.4,6.9]]){join.box(x,.33,z,.5,.48,.5,C.iron);join.beam([x,2.6,z],[x-.85,3.3,z],.11,C.wood);join.box(x-.5,3.34,z,1.55,.3,.38,C.beam);for(const y of[.2,.42,3.35])join.box(x+.26,y,z,.045,.09,.13,C.brass);}
 for(let a=.3;a<3;a+=.55){const x=-4+3.55*Math.cos(a),z=4.5+3.55*Math.sin(a);join.box(x,3.8,z,.35,.3,.35,C.iron);}
 // Deep reveal trim follows existing openings; shutters stay outside the route.
 for(const x of[-.12,1.42])join.box(x,1.23,4.04,.18,2.46,.28,C.beam);join.box(.65,2.53,4.04,1.78,.2,.38,C.wood);
 mesh(join);
 const doorstep=field('door-step',.05,'structure',0);doorstep.box(.65,.065,4.2,1.8,.13,.66,C.board);mesh(doorstep);
 const hand=field('hand-objects',.025,'props',0);
 function cup(x,y,z,c,s=1){hand.cylinder(x,y+.1*s,z,.105*s,.2*s,c,.025);hand.cylinder(x,y+.014,z,.095*s,.028,c);const a=Math.sin(x*3+z)*1.1,point=(r,h)=>[x+Math.cos(a)*r*s,y+h*s,z+Math.sin(a)*r*s];hand.beam(point(.1,.035),point(.18,.035),.022,c);hand.beam(point(.18,.035),point(.18,.17),.022,c);hand.beam(point(.18,.17),point(.09,.17),.022,c);}
 for(const[x,z,c]of[[-5.1,1.2,32],[-3.2,2.05,15],[-4.35,1.18,28]])cup(x,.96,z,c);hand.cylinder(-4.3,1,1.95,.29,.07,28);hand.ellipsoid(-4.35,1.1,1.95,.2,.09,.12,23);hand.box(-5.35,.994,1.9,.47,.05,.52,25);
 for(let i=0;i<5;i++){cup(-7.95+i*.4,1.75,-2.5,32,.7);hand.beam([-7.95+i*.4,2.08,-2.5],[-7.95+i*.4,1.93,-2.5],.024,C.iron);}
 for(let j=0;j<3;j++)for(let i=0;i<5;i++){const y=.45+j*.57,z=-5.35+i*.25;hand.cylinder(-1.45,y+.16,z,.1,.3,[25,15,28][j]);hand.cylinder(-1.45,y+.32,z,.105,.035,C.wood);}
 for(let i=0;i<13;i++){const x=-5.8+i*.13;hand.box(x,2.3,-6.76,.105,.26+.1*hash(i,1,0),.22,[3,14,25,29,35][i%5]);hand.box(x,2.29,-6.64,.11,.026,.027,28);}hand.box(-5,2.06,-6.76,2,.12,.4,C.wood);
 hand.box(-4,.027,1.55,4.7,.035,3.3,25);for(const z of[.12,2.98]){hand.box(-4,.051,z,4.7,.017,.07,28);hand.box(-4,.051,z+(z<1?.15:-.15),4.7,.017,.06,3);}for(let x=-6.2;x<-1.8;x+=.24)hand.box(x,.051,.36,.055,.025,.18,28);
 hand.box(6.3,.84,5.1,1.05,.025,.65,28);for(let i=0;i<5;i++){hand.box(7.15+i*.16,.9,5.5,.08,.09,.42,C.iron);hand.box(7.15+i*.16,.9,5.68,.09,.09,.12,C.wood);}hand.cylinder(5.65,1.02,5.38,.18,.32,16,.04);hand.beam([8.42,1.22,5.6],[8.62,1.22,5.6],.04,16);
 mesh(hand);
 const landingSupport=field('stair-foot-braces',.1,'structure',0);for(const z of[7.6,8.2])landingSupport.beam([11.6,-.22,z],[9.3,-1.5,4.8],.16,C.beam);mesh(landingSupport);
 const upperProps=field('bedroom-objects',.05,'props',1);for(let i=0;i<7;i++){upperProps.box(-4.8+i*.1,4.79,2.68,.08,.2+.1*hash(i,4,2),.22,[25,29,3,35][i%4]);}upperProps.box(-.1,4.7,-4.04,.7,.08,1.55,27);for(let i=0;i<4;i++)upperProps.box(-.45+i*.2,4.75,-4.02,.045,.025,1.5,29);upperProps.cylinder(-4.1,4.82,2.43,.12,.25,15,.05);mesh(upperProps);
 const lamps=field('lamps',.05,'lamps',0);for(const[x,y,z]of[[-5.9,2.8,-3],[-1,2.8,1.1],[8.6,2.6,3.7],[-3.5,6.1,2.9]]){lamps.box(x,y,z,.3,.38,.3,33);for(const a of[-1,1])for(const b of[-1,1])lamps.box(x+a*.17,y,z+b*.17,.05,.5,.05,C.iron);lamps.box(x,y+.28,z,.43,.13,.43,C.iron);lamps.box(x,y-.28,z,.42,.1,.42,C.iron);lamps.beam([x,y+.32,z],[x,y+.7,z],.026,C.iron);}mesh(lamps);
 }
};
