// Test rendering with a minimal mock DOM, no browser or npm modules.
// Run: node tests/frontend_dom_smoke.cjs /tmp/jalanyuk_dom_sample.json
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const path=require('node:path');
const code=fs.readFileSync(path.resolve(__dirname,'../static/app.js'),'utf8');
const imported=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const plan=imported.plan||imported;
const nodes=new Map(),data=new Map();
function node(id){if(nodes.has(id))return nodes.get(id);
  const result={id,value:'',checked:false,hidden:false,innerHTML:'',textContent:'',dataset:{},style:{},disabled:false,
    classList:{add(){},remove(){},toggle(){}},addEventListener(){},querySelectorAll(){return[]},closest(){return result},
    appendChild(){},append(){},click(){},scrollIntoView(){},showModal(){},close(){}};
  nodes.set(id,result);return result;}
const context=vm.createContext({
 document:{getElementById:node,querySelectorAll(){return[]},querySelector(){return node('selector')},createElement(){return node('created')},body:{appendChild(){}}},
 window:{addEventListener(){},open(){}},
 navigator:{},location:{pathname:'/',origin:'http://localhost:8000',protocol:'http:',hostname:'localhost'},
 localStorage:{getItem(k){return data.get(k)||null},setItem(k,v){data.set(k,v)}},
 crypto:crypto.webcrypto,URL,Intl,Date,Math,Number,String,JSON,Array,Object,Set,Map,Error,Uint8Array,
 setTimeout(){return 1},clearTimeout(){},console
});
vm.runInContext(code,context,{filename:'static/app.js'});
context.testPlan=plan;
vm.runInContext('fillCfg(testPlan.config);showPlan(testPlan);',context);
const dayHtml=node('dayContent').innerHTML;
const travelHtml=node('travelSteps').innerHTML;
if(!travelHtml.includes('31 Des') || !travelHtml.includes('1 Jan')) throw Error('Tanggal lintas tahun tidak muncul.');
if(!dayHtml.includes('Jam kegiatan:')) throw Error('Jam kegiatan harian tidak muncul.');
if(!node('breakdown').innerHTML.includes('Transportasi antarkota PP')) throw Error('Rincian transport tidak muncul.');
const cfg=vm.runInContext('readCfg()',context);
if(cfg.infants_under_2!==1||cfg.children_age_2!==1||cfg.depart_date!=='2026-12-31')throw Error('Data family & dates tidak dapat dimuat ulang.');
vm.runInContext('st.day=2; renderDay();',context);
if(!node('dayContent').innerHTML.includes('Batas keberangkatan pulang'))throw Error('Batas jadwal kepulangan tidak muncul.');
if(plan.itinerary[2].slots.some(x=>x.status==='tidak_terjadwal')&&!node('dayContent').innerHTML.includes('Tidak terjadwal'))throw Error('Aktivitas di luar batas kepulangan tidak ditandai.');
console.log('Frontend DOM smoke: PASS. Timeline, family fields, budget, return-day warnings verified.');
