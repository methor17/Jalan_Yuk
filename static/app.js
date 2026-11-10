'use strict';
// JalanYuk 2.5: UI tanpa framework; kalkulasi dijalankan Python (server).
const $=id=>document.getElementById(id);
const money=n=>'Rp'+new Intl.NumberFormat('id-ID',{maximumFractionDigits:0}).format(Math.round(Number(n)||0));
const safe=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtDate=s=>{try{return new Date(s+'T12:00:00').toLocaleDateString('id-ID',{day:'numeric',month:'short',year:'numeric'});}catch{return s;}};
const num=id=>Number($(id).value)||0;
const keyName='jalanyuk-client-key-v2';
function identity(){let k=localStorage.getItem(keyName);if(k&&k.length>30)return k;const b=new Uint8Array(32);crypto.getRandomValues(b);k=Array.from(b,v=>v.toString(16).padStart(2,'0')).join('');localStorage.setItem(keyName,k);return k;}
const clientKey=identity();
const st={location:null,places:[],weather:{days:[]},plan:null,day:0,tripId:null,shareId:null,shared:null,readOnly:false,selection:null,map:null,mapRoute:null,modalPlaces:[],lastCity:'',isLoading:false,previousPlan:null,hotelReturnTimes:{},routeCache:{},hotelHits:[],routingBusy:false,routingEpoch:0};
let toastHandle;
function toast(msg){$('toast').textContent=msg;$('toast').classList.add('show');clearTimeout(toastHandle);toastHandle=setTimeout(()=>$('toast').classList.remove('show'),3800);}
function notice(msg,type='warn'){$('noticeBar').hidden=!msg;$('noticeBar').className='notice-bar '+(type==='error'?'error':'');$('noticeBar').textContent=msg||'';}
async function api(url,body,method){const controller=new AbortController(),t=setTimeout(()=>controller.abort(),(url.includes('/api/routes/refresh')?100000:31000));try{const opt={method:method||(body?'POST':'GET'),headers:{'X-Client-Key':clientKey},signal:controller.signal};if(body!==undefined&&body!==null){opt.headers['Content-Type']='application/json';opt.body=JSON.stringify(body);}const res=await fetch(url,opt);const data=await res.json();if(!res.ok)throw Error(data?.error||`HTTP ${res.status}`);return data;}catch(e){if(e.name==='AbortError')throw Error('Permintaan terlalu lama. Periksa koneksi internet lalu coba lagi.');throw e;}finally{clearTimeout(t);}}
const today=()=>{const d=new Date(),offset=d.getTimezoneOffset()*60000;return new Date(d.getTime()-offset).toISOString().slice(0,10);};
function readCfg(){return {
 city:$('destination').value.trim(),city_lat:st.location?.lat??null,city_lon:st.location?.lon??null,origin:$('origin').value.trim(),
 depart_date:$('departDate').value,depart_time:$('departTime').value,
 destination_arrival_date:$('destinationArrivalDate').value,destination_arrival_time:$('destinationArrivalTime').value,
 start_date:$('startDate').value,arrival_time:$('arrival').value,
 return_date:$('returnDate').value,return_time:$('returnTime').value,
 home_arrival_date:$('homeArrivalDate').value,home_arrival_time:$('homeArrivalTime').value,
 return_buffer_minutes:num('returnBuffer'),daily_start_time:$('dailyStartTime').value,days:num('days'),
 budget:num('budget'),adults:num('adults'),children:num('children'),children_2_plus:num('children'),children_age_2:num('childrenAge2'),
 infants_under_2:num('infants'),seniors:num('seniors'),pace:$('pace').value,
 interests:Array.from(document.querySelectorAll('#interestOptions input:checked')).map(x=>x.value),
 include_hotel:$('includeHotel').checked,hotel_rate:num('hotelRate'),room_capacity:num('roomCapacity'),infant_uses_bed:$('infantUsesBed').checked,
 outbound_mode:$('outboundMode').value,outbound_fare:num('outboundFare'),return_mode:$('returnMode').value,return_fare:num('returnFare'),car_capacity:num('carCapacity'),
 train_infant_without_seat:$('trainInfantWithoutSeat').checked,train_age2_without_seat:$('trainAge2WithoutSeat').checked,
 flight_infant_percent:num('flightInfantPercent'),other_infant_percent:num('otherInfantPercent'),
 child_activity_percent:num('childActivityPercent'),infant_activity_percent:num('infantActivityPercent'),
 child_food_percent:num('childFoodPercent'),infant_food_percent:num('infantFoodPercent'),age2_activity_percent:num('age2ActivityPercent'),age2_food_percent:num('age2FoodPercent'),
 local_per_person_day:num('localRate'),local_child_percent:num('localChildPercent'),local_infant_percent:num('localInfantPercent'),local_age2_percent:num('localAge2Percent'),
 parking_per_day:num('parking'),miscellaneous:num('misc'),emergency_fund:num('emergency'),
 base_name:$('hotelName').value.trim(),hotel_area:$('hotelArea').value.trim(),
 base_lat:$('hotelLat').value===''?null:num('hotelLat'),base_lon:$('hotelLon').value===''?null:num('hotelLon'),
 use_city_center_as_base:$('useCityBase').checked,return_to_base:$('returnHotel').checked,
 include_evening:$('includeEvening').checked,night_start_time:$('nightStart').value,
 daily_hotel_return_time:$('hotelReturnDefault').value,
 hotel_return_times:Object.fromEntries(Object.entries(st.hotelReturnTimes).filter(([d])=>d>=$('startDate').value&&d<=$('returnDate').value)),
 last_day_via_hotel:$('lastViaHotel').checked,
 return_hub_name:$('returnHubName').value.trim(),
 return_hub_lat:$('returnHubLat').value===''?null:num('returnHubLat'),return_hub_lon:$('returnHubLon').value===''?null:num('returnHubLon'),
 local_travel_mode:$('localTravelMode').value,local_cost_mode:$('localCostMode').value,
 local_cost_per_km:num('localPerKm'),local_base_per_leg:num('localBaseLeg'),
 local_vehicle_capacity:num('localCapacity'),traffic_percent:num('trafficPercent'),
 routing_provider:$('routingProvider').value,local_utc_offset:num('localUtcOffset'),route_safety_minutes:num('routeSafety'),unknown_leg_minutes:num('unknownLegMinutes'),
 visit_gap_minutes:num('visitGap'),route_cache:st.routeCache,leg_overrides:st.plan?.config?.leg_overrides||{} };}
function fillCfg(c){
 $('destination').value=c.city||'';$('origin').value=c.origin||'';
 const begin=c.start_date||today(),duration=c.days||3,returnDate=c.return_date||addDays(begin,duration-1);
 [['departDate',c.depart_date||begin],['departTime',c.depart_time||'06:00'],
 ['destinationArrivalDate',c.destination_arrival_date||begin],['destinationArrivalTime',c.destination_arrival_time||'08:00'],
 ['startDate',begin],['arrival',c.arrival_time||'09:00'],['days',duration],['dailyStartTime',c.daily_start_time||'09:00'],
 ['returnDate',returnDate],['returnTime',c.return_time||'20:00'],
 ['homeArrivalDate',c.home_arrival_date||returnDate],['homeArrivalTime',c.home_arrival_time||'23:00'],
 ['returnBuffer',c.return_buffer_minutes??90],['budget',c.budget??3000000],
 ['adults',c.adults??2],['seniors',c.seniors??0],['children',c.children_2_plus??c.children??0],['childrenAge2',c.children_age_2??0],['infants',c.infants_under_2??0],
 ['pace',c.pace||'normal'],['hotelRate',c.hotel_rate??350000],['roomCapacity',c.room_capacity??2],
 ['outboundMode',c.outbound_mode||'lainnya'],['returnMode',c.return_mode||'lainnya'],
 ['outboundFare',c.outbound_fare??Math.floor((c.intercity_per_person??200000)/2)],
 ['returnFare',c.return_fare??Math.ceil((c.intercity_per_person??200000)/2)],['carCapacity',c.car_capacity??5],
 ['flightInfantPercent',c.flight_infant_percent??10],['otherInfantPercent',c.other_infant_percent??0],
 ['childActivityPercent',c.child_activity_percent??70],['infantActivityPercent',c.infant_activity_percent??0],
 ['childFoodPercent',c.child_food_percent??70],['infantFoodPercent',c.infant_food_percent??0],['age2ActivityPercent',c.age2_activity_percent??c.child_activity_percent??70],['age2FoodPercent',c.age2_food_percent??c.child_food_percent??70],
 ['localRate',c.local_per_person_day??50000],['localChildPercent',c.local_child_percent??100],['localInfantPercent',c.local_infant_percent??0],['localAge2Percent',c.local_age2_percent??c.local_child_percent??100],
 ['parking',c.parking_per_day??15000],['misc',c.miscellaneous??100000],['emergency',c.emergency_fund??150000],
 ['hotelName',c.base_name||''],['hotelArea',c.hotel_area||''],['hotelLat',c.base_lat??''],['hotelLon',c.base_lon??''],
 ['nightStart',c.night_start_time||'18:00'],['hotelReturnDefault',c.daily_hotel_return_time||'21:00'],
 ['returnHubName',c.return_hub_name||''],['returnHubLat',c.return_hub_lat??''],['returnHubLon',c.return_hub_lon??''],
 ['localTravelMode',c.local_travel_mode||'mobil'],['localCostMode',c.local_cost_mode||'per_km'],
 ['localPerKm',c.local_cost_per_km??2500],['localBaseLeg',c.local_base_per_leg??6000],
 ['localCapacity',c.local_vehicle_capacity??5],['trafficPercent',c.traffic_percent??125],['visitGap',c.visit_gap_minutes??15],
 ['routingProvider',c.routing_provider==='google'?'multi':(c.routing_provider||'multi')],['routeSafety',c.route_safety_minutes??10],['unknownLegMinutes',c.unknown_leg_minutes??45],['localUtcOffset',c.local_utc_offset??7]].forEach(([id,val])=>$(id).value=val);
 st.hotelReturnTimes={...(c.hotel_return_times||{})};st.routeCache={...(c.route_cache||{})};
 $('returnHotel').checked=c.return_to_base!==false;$('useCityBase').checked=c.use_city_center_as_base!==false;
 $('includeEvening').checked=c.include_evening!==false;$('lastViaHotel').checked=c.last_day_via_hotel===true;
 $('includeHotel').checked=c.include_hotel!==false;$('infantUsesBed').checked=c.infant_uses_bed===true;
 $('trainInfantWithoutSeat').checked=c.train_infant_without_seat!==false;$('trainAge2WithoutSeat').checked=c.train_age2_without_seat!==false;
 document.querySelectorAll('#interestOptions input').forEach(x=>x.checked=(c.interests||[]).includes(x.value));
 st.location=c.city_lat!=null&&c.city_lon!=null?{lat:c.city_lat,lon:c.city_lon,name:c.city}:null;
 st.lastCity=c.city||'';$('cityHint').textContent=st.location?'✓ Koordinat kota dipilih. Pencarian lokasi siap.':'Pilih Cari jika ingin mencari koordinat baru.';
}
function openDialog(id){$(id).showModal();}
function closeDialog(id){$(id).close();}
function setBusy(el,busy,label){if(!el)return;el.disabled=busy;if(busy){el.dataset.oldLabel=el.innerHTML;el.textContent=label||'Memproses...';}else if(el.dataset.oldLabel){el.innerHTML=el.dataset.oldLabel;delete el.dataset.oldLabel;}}

async function searchCity(){const q=$('destination').value.trim();if(q.length<2){toast('Ketik nama kota atau tujuan terlebih dahulu.');return;}const btn=$('findCityBtn');setBusy(btn,true,'Mencari…');$('cityMatches').hidden=true;try{const data=await api('/api/geocode?q='+encodeURIComponent(q));const hits=$('cityMatches');hits.innerHTML='';if(!data.locations.length){hits.textContent='Lokasi tidak ditemukan. Coba nama lain.';hits.hidden=false;return;}data.locations.forEach(loc=>{const b=document.createElement('button');b.type='button';b.textContent='📍 '+loc.name;b.addEventListener('click',()=>selectLocation(loc,q));hits.appendChild(b);});hits.hidden=false;if(data.fallback)notice('Pencarian peta tidak terhubung. Menggunakan koordinat kota contoh sebagai cadangan; verifikasi lokasi sebelum pergi.');}catch(e){notice(e.message+' Kota tetap bisa diketik dan tempat dapat ditambahkan manual.','error');toast(e.message);}finally{setBusy(btn,false);}}
function selectLocation(loc,city){if(st.lastCity&&st.lastCity!==city){['hotelName','hotelArea','hotelLat','hotelLon'].forEach(id=>$(id).value='');st.hotelReturnTimes={};}st.location={lat:loc.lat,lon:loc.lon,name:loc.name};st.lastCity=city;$('destination').value=city;$('cityMatches').hidden=true;$('cityHint').textContent='✓ '+loc.name+' — sumber lokasi peta';st.places=[];st.weather={days:[]};toast('Lokasi tujuan dipilih. Klik Buat Rencana.');}
async function ensureLocation(city){if(st.location&&city===st.lastCity)return;st.location=null;st.places=[];st.weather={days:[]};try{const r=await api('/api/geocode?q='+encodeURIComponent(city));if(r.locations.length){st.location={lat:r.locations[0].lat,lon:r.locations[0].lon,name:r.locations[0].name};st.lastCity=city;if(r.fallback)notice('Koordinat cadangan digunakan. Data lokasi live belum tersedia.');$('cityHint').textContent='✓ '+r.locations[0].name;}}catch(e){notice('Pencarian kota belum tersedia: '+e.message+' Masih bisa membuat itinerary manual/berdasarkan katalog contoh.');}}
async function getPlaces(city){if(st.places.length)return st.places;let places=[],source='';if(st.location){try{const data=await api('/api/discover?lat='+st.location.lat+'&lon='+st.location.lon+'&radius=12000');places=data.places||[];source=data.source; if(places.length<6)notice('Hasil peta hanya '+places.length+' lokasi. Kamu bisa mencari nama tempat lain atau menambahkan manual.');}catch(e){notice('Layanan pencarian wisata dinamis sedang tidak tersedia. '+e.message+' Dicoba katalog contoh.');}}
if(places.length<6){try{const c=await api('/api/curated?city='+encodeURIComponent(city));const ids=new Set(places.map(p=>p.name.toLowerCase()));places.push(...(c.places||[]).filter(p=>!ids.has(p.name.toLowerCase())));if(c.places?.length)source=source?'OSM + katalog contoh':'Katalog contoh (offline)';}catch{}}
st.places=places;$('placeSource').textContent=source||'Input manual / data belum tersedia';return places;}
async function getWeather(cfg){if(!st.location)return {days:[]};try{return await api('/api/weather?lat='+st.location.lat+'&lon='+st.location.lon+'&start_date='+encodeURIComponent(cfg.start_date)+'&days='+cfg.days);}catch{return {days:[],notice:'Cuaca belum tersedia.'};}}
async function generate(e){if(e)e.preventDefault();if(st.readOnly){toast('Ini rencana berbagi (hanya baca). Buat perjalanan baru untuk mengedit.');return;}
 st.routingEpoch++;
 const city=$('destination').value.trim();if(city.length<2){toast('Masukkan kota tujuan lebih dahulu.');$('destination').focus();return;}
 if(num('adults')+num('children')+num('infants')+num('seniors')<1){toast('Isi minimal satu wisatawan.');return;}
 if(num('childrenAge2')>num('children')){toast('Anak yang tepat 2 tahun tidak boleh lebih dari total anak ≥2 tahun.');return;}
 const btn=$('generateBtn');setBusy(btn,true,'Mencari tempat dan menyusun rute…');try{
 validateTripInput(readCfg());await ensureLocation(city);const cfg=readCfg();await getPlaces(city);st.weather=await getWeather(cfg);
 const plan=await api('/api/plan',{config:cfg,places:st.places,weather:st.weather});
 st.tripId=null;st.shareId=null;st.shared=null;showPlan(plan);
 if($('autoRouteOnGenerate').checked)await refreshRoutes(null,false);
 if(!st.places.length)notice('Belum ada hasil wisata untuk kota ini. Gunakan Tambah Tempat untuk mencari atau menambah lokasi manual.');
 else if(st.places.every(p=>p.source==='Katalog contoh JalanYuk'))notice('Hasil ini katalog contoh. Harga dan posisi tiap tempat perlu diverifikasi.');
 else notice('Rekomendasi waktu pagi–malam dan perpindahan hotel/objek wisata merupakan estimasi; pilih hotel agar perhitungan jarak realistis.');
 document.querySelector('.results').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(err){notice('Rencana tidak dapat dibuat: '+err.message,'error');toast(err.message);}finally{setBusy(btn,false);}
}
function safeTripSnapshot(plan){
 // Python validates and strips legacy Google-derived estimates on load.
 return plan;
}
function showPlan(plan){st.plan=plan;st.weather=plan.weather||st.weather;st.day=Math.min(st.day,Math.max(0,plan.itinerary.length-1));
 $('emptyState').hidden=true;$('planView').hidden=false;
 $('tripMeta').textContent='ITINERARY CERDAS · '+plan.config.days+' HARI KEGIATAN';$('planTitle').textContent='Jelajahi '+plan.config.city+' ✦';
 const c=plan.config;$('planSubtitle').textContent=fmtDate(c.start_date)+' – '+fmtDate(c.return_date)+' • '+plan.summary.persons+' wisatawan • '+(st.readOnly?'Rencana dibagikan':'Bisa disesuaikan kapan saja');
 $('metricTotal').textContent=money(plan.summary.total);$('metricRemaining').textContent=money(Math.abs(plan.summary.remaining));$('metricRemaining').closest('.metric').classList.toggle('negative',plan.summary.remaining<0);
 $('remainingLabel').textContent=plan.summary.remaining<0?'Kekurangan budget':'Sisa anggaran';$('remainingCaption').textContent=plan.summary.remaining<0?'Anggaran perlu disesuaikan':'Perkiraan sisa dana';
 const count=plan.itinerary.reduce((sum,day)=>sum+day.slots.filter(v=>v.item&&v.status==='scheduled').length,0);
 $('metricPlaces').textContent=count+' tempat';$('metricDays').textContent=plan.config.days+' hari wisata';
 renderTravelSteps();renderSummary();renderDayTabs();renderDay();renderWeather();
 $('mapBtn').disabled=false;
 $('mapBtn').textContent=$('map').hidden?'🗺 Tampilkan peta':'✕ Sembunyikan peta';
 $('mapPlaceholder').innerHTML='<div class="map-symbol">⌖</div><p>Klik “Tampilkan peta” untuk melihat lokasi dari OpenStreetMap.</p><small>Estimasi rute tidak mencakup kemacetan aktual.</small>';
 renderMapIfShown();
 try{localStorage.setItem('jalanyuk-local-backup',JSON.stringify({plan:safeTripSnapshot(st.plan),places:st.places,weather:st.weather,updated:Date.now()}));}catch{}
}
function renderTravelSteps(){const t=st.plan.summary.travel_timeline||{},items=[['Berangkat dari asal',t.berangkat],['Tiba kota wisata',t.tiba_tujuan],['Mulai wisata',t.mulai_wisata],['Berangkat pulang',t.berangkat_pulang],['Tiba kembali',t.tiba_rumah]];
 $('travelSteps').innerHTML=items.map(([name,datetime])=>`<div class="travel-step"><small>${safe(name)}</small><strong>${safe(datetime?fmtDate(datetime.slice(0,10))+' · '+datetime.slice(11):'—')}</strong></div>`).join('');
}
function renderSummary(){const s=st.plan.summary;const pct=s.budget>0?Math.min(100,s.total/s.budget*100):100;
 $('summaryTotal').textContent=money(s.total);$('budgetBar').style.width=pct+'%';$('budgetBar').classList.toggle('over',s.remaining<0);$('budgetStatus').classList.toggle('over',s.remaining<0);
 $('budgetStatus').textContent=(s.remaining<0?'✕ Melebihi budget '+money(-s.remaining):'✓ Sisa budget '+money(s.remaining));
 const lines=[['wisata','Tiket & wisata'],['kuliner','Kuliner & makan'],['hotel',`Penginapan (${s.rooms} kamar × ${s.nights} malam)`],
 ['transport_antar_kota','Transportasi antarkota PP'],['transport_lokal','Transportasi lokal'],['parkir','Parkir'],['lain_lain','Biaya lain'],['dana_cadangan','Dana cadangan']];
 const transports=s.transport_detail||{};
 $('breakdown').innerHTML=lines.map(([key,label])=>`<div class="cost-line"><span>${safe(label)}</span><strong>${money(s.breakdown[key])}</strong></div>`).join('')+
 (transports.pergi?`<div class="transport-split">↗ Pergi (${safe(transports.pergi.mode)}): ${money(transports.pergi.total)}<br>↙ Pulang (${safe(transports.pulang.mode)}): ${money(transports.pulang.total)}<br><small>Infant gratis KAI jika tidak menggunakan kursi dan memenuhi syarat pendamping. Biaya pesawat dan moda lain adalah asumsi.</small></div>`:'');
 $('suggestions').innerHTML=(s.suggestions.length?s.suggestions:['Rencana masih dalam anggaran. Kamu bisa menyimpan dana untuk kebutuhan mendadak.']).slice(0,9).map((m,i)=>`<div class="tip-item">${i===0?'✦':'•'} ${safe(m)}</div>`).join('');
}
function renderDayTabs(){const root=$('dayTabs');root.innerHTML=st.plan.itinerary.map((d,i)=>`<button role="tab" aria-selected="${st.day===i}" class="${st.day===i?'active':''}" data-day="${i}">Hari ${d.day}<small>${safe(fmtDate(d.date).replace(/ \d{4}$/,''))}</small></button>`).join('');root.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{st.day=Number(b.dataset.day);renderDayTabs();renderDay();}));}
function legSourceLabel(s){return s==='osrm_driving'?'OSRM · jaringan jalan + buffer':s==='osrm_distance_estimated_speed'?'Perkiraan kecepatan dari jarak OSRM':s==='multi_source_max'?'Estimasi terlama dari sumber yang ada':s==='openrouteservice'?'OpenRouteService':s==='manual'?'Diisi manual':s==='approx_distance'?'Perkiraan jarak lurus':'Koordinat tidak lengkap';}
function routeConfidenceLabel(leg){if(leg?.source!=='multi_source_max')return '';const count=leg.samples?.length||0;return count===0?' · belum ada respons penyedia: model jarak':count===1?' · 1 sumber + buffer konservatif':' · '+count+' penyedia dibandingkan';}
function routeAttribution(leg){return '';}
function googleDirections(leg){
 if(!leg?.start_coords||!leg?.end_coords)return '';
 const a=leg.start_coords,b=leg.end_coords;
 const mode=leg.mode==='jalan'?'walking':leg.mode==='sepeda'?'bicycling':leg.mode==='transit'?'transit':'driving';
 return 'https://www.google.com/maps/dir/?api=1&origin='+encodeURIComponent(a.lat+','+a.lon)+'&destination='+encodeURIComponent(b.lat+','+b.lon)+'&travelmode='+mode;
}
function renderDay(){const day=st.plan.itinerary[st.day],w=day.weather||{};const count=day.slots.filter(s=>s.status==='scheduled').length;
 let html=`<div class="day-context"><span><strong>${safe(fmtDate(day.date))}</strong> · ${count} aktivitas terjadwal · ${money(day.cost)} · 🚗 ${safe(day.travel_minutes_total)} menit / ${safe(day.travel_km_estimate)} km</span><span class="weather-inline">${w.rain_probability==null?'☁ Cuaca belum tersedia':(w.rain_probability>=60?'☔':'☀')+' Kemungkinan hujan '+w.rain_probability+'%'}</span></div>`;
 html+=`<div class="day-window">🕒 Jam kegiatan: ${safe(day.window_start)} – ${safe(day.window_end)}${day.is_return_day?' · Batas keberangkatan pulang':' · Tiba kembali di hotel selambatnya '+safe(day.hotel_return_target)}</div>
 <div class="day-hotel-editor"><div><strong>🏨 Rencana kembali ke hotel</strong><small>${day.is_return_day&&!st.plan.config.last_day_via_hotel?'Hari terakhir langsung menuju titik kepulangan, kecuali opsi mampir hotel diaktifkan.':'Atur target tiba di hotel untuk tanggal ini.'}</small></div><input id="dayHotelReturn" type="time" value="${safe(st.hotelReturnTimes[day.date]||day.hotel_return_target||'21:00')}" ${st.readOnly||(day.is_return_day&&!st.plan.config.last_day_via_hotel)?'disabled':''} aria-label="Jam kembali ke hotel hari ini"></div>
 <div class="route-timeline">`;
 day.slots.forEach((slot,i)=>{
 const place=slot.item,skipped=slot.status==='tidak_terjadwal',time=slot.start||(skipped?'Tidak terjadwal':'—');const cat=slot.kind==='kuliner'?'Kuliner':'Wisata';const isFood=slot.kind==='kuliner';
 const mapLink=place?`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.lat!=null?place.lat+','+place.lon:place.name+' '+st.plan.config.city)}`:'';
 html+=`<div class="activity ${skipped?'activity-not-scheduled':''}"><div class="act-pin ${isFood?'food':''}">${isFood?'🍜':'✦'}</div><div class="act-main"><span class="act-time">${safe(time)} ${slot.start?`– ${safe(slot.end)} · ${cat}`:skipped?'· tidak masuk itinerary berbayar':`· Pilih ${cat.toLowerCase()}`}</span>${slot.leg?`<div class="travel-line">🚗 ${routeAttribution(slot.leg)}${safe(slot.leg.from)} → ${safe(slot.leg.to)} · ${slot.leg.minutes==null?'Belum ada ETA — alokasi '+slot.leg.reserved_minutes+' menit':slot.leg.minutes+' menit · '+(slot.leg.km==null?'jarak belum tersedia':slot.leg.km+' km')} · ${safe(legSourceLabel(slot.leg.source))}${safe(routeConfidenceLabel(slot.leg))} ${slot.leg.samples?.length?' · '+safe(slot.leg.samples.map(x=>legSourceLabel(x.source)+': '+x.minutes+' m').join(' / '))+' · cadangan '+slot.leg.safety_minutes+' m':''} · ${safe(slot.leg.depart||'—')}–${safe(slot.leg.arrive||'—')}${slot.leg.waiting_minutes?' · tunggu '+slot.leg.waiting_minutes+' menit':''}${slot.leg.estimated_cost?' · '+money(slot.leg.estimated_cost):''} ${googleDirections(slot.leg)?`<a href="${safe(googleDirections(slot.leg))}" target="_blank" rel="noopener noreferrer">↗ Rute Google Maps</a>`:''}</div>`:''}
 <div class="act-card ${place?'':'empty-activity'} ${skipped?'not-scheduled':''}">${place?`<div class="act-name">${safe(place.name)}</div><span class="act-theme">${safe(place.theme||cat)}</span><div class="act-info">📍 ${safe(place.area||st.plan.config.city)} ${place.duration?'· ⏱ '+place.duration+' menit':''}</div>
 <div class="act-info">🧭 ${place.lat!=null&&place.lon!=null?'Koordinat: '+safe(Number(place.lat).toFixed(5))+', '+safe(Number(place.lon).toFixed(5)):'Koordinat belum ada — cari lokasi sebelum hitung rute'}</div>
 ${place.opening_hours?`<div class="act-info">🕒 Jam buka terdata: ${safe(place.opening_hours)} (cek kembali)</div>`:''}${place.wheelchair==='yes'?'<div class="act-info">♿ Akses kursi roda tercatat di OSM</div>':''}
 <div class="act-fee">${money(slot.cost)} <small>${skipped?'Belum masuk budget · ':''}${money(place.price)} / orang (dasar)</small></div>${slot.schedule_warning?`<span class="schedule-warn">⚠ ${safe(slot.schedule_warning)}</span>`:''}${slot.weather_warning?`<span class="act-warning">☔ ${safe(slot.weather_warning)}</span>`:''}${slot.opening_warning?`<span class="act-warning">🕒 ${safe(slot.opening_warning)}</span>`:''}`:
 `<div class="act-name">Slot ${cat.toLowerCase()} belum terisi</div><div class="act-info">Cari destinasi / kuliner yang ingin dikunjungi.</div>`}
 <div class="act-actions"><button data-op="change" data-i="${i}">⌕ ${place?'Ganti':'Cari tempat'}</button>${place?`<button data-op="price" data-i="${i}">✎ Edit Rp</button><button data-op="locate" data-i="${i}">📍 ${place.lat==null?'Cari koordinat':'Perbaiki titik'}</button><button data-op="remove" data-i="${i}">✕ Hapus</button><a href="${safe(mapLink)}" target="_blank" rel="noopener noreferrer">↗ Maps</a>`:''}</div></div></div></div>`;
 });html+='</div>';
 const endings=(day.travel_legs||[]).filter(l=>l.kind);
 if(endings.length)html+='<div class="end-legs">'+endings.map(l=>`<div class="travel-line">${l.kind==='hotel'?'🏨 Kembali hotel':'🚉 Menuju lokasi keberangkatan'} · ${safe(l.from)} → ${safe(l.to)} · ${l.minutes==null?'ETA belum diketahui — alokasi '+l.reserved_minutes+' menit':l.minutes+' menit / '+l.km+' km'} · tiba ${safe(l.arrive||'—')} ${l.estimated_cost?' · '+money(l.estimated_cost):''} · ${routeAttribution(l)}${safe(legSourceLabel(l.source))}${safe(routeConfidenceLabel(l))} ${googleDirections(l)?`<a href="${safe(googleDirections(l))}" target="_blank" rel="noopener noreferrer">↗ Rute Google Maps</a>`:''}</div>`).join('')+'</div>';
 if(day.warnings?.length)html+=`<div class="route-info">⚠ ${day.warnings.map(safe).join('<br>⚠ ')}</div>`;
 $('dayContent').innerHTML=html;
 $('dayHotelReturn').addEventListener('change',async e=>{if(st.readOnly)return;st.hotelReturnTimes[day.date]=e.target.value;await recalc();toast('Jam kembali ke hotel dan itinerary dihitung ulang.');});
 $('dayContent').querySelectorAll('button[data-op]').forEach(btn=>btn.addEventListener('click',async()=>{
 if(st.readOnly){toast('Ini rencana berbagi. Edit tersedia pada rencana milik sendiri.');return;}
 const i=Number(btn.dataset.i),op=btn.dataset.op;if(op==='change')openPlace(st.day,i);else if(op==='price')openPrice(st.day,i);else if(op==='locate')await fixPlaceCoordinate(st.day,i);
 else if(op==='remove'){st.plan.itinerary[st.day].slots[i].item=null;await recalc();}
 }));$('routeInfo').hidden=true;
}
function renderWeather(){const d=st.plan.weather?.days||[];$('weatherInfo').innerHTML=d.length?d.map(w=>`<div class="weather-row"><span>${safe(fmtDate(w.date))}</span><strong>${w.rain_probability==null?'—':(w.rain_probability>=60?'☔':'☀')+' '+w.rain_probability+'%'} ${w.temperature_max!=null?'· '+w.temperature_max+'°C':''}</strong></div>`).join(''):'<p class="small-note">Prakiraan maksimal sekitar 16 hari dari hari ini dan memerlukan koneksi internet.</p>';}
async function recalc(reorder=false){
 if(!st.plan)return;
 st.routingEpoch++;
 try{
  const cfg=readCfg();st.plan=await api('/api/recalculate',{config:cfg,itinerary:st.plan.itinerary,weather:st.weather,reorder});showPlan(st.plan);
  if(reorder)toast('Urutan lokasi sejenis dioptimalkan berdasarkan kedekatan koordinat.');
  if($('autoRouteOnGenerate').checked&&!st.routingBusy&&!st.readOnly)await refreshRoutes(st.day,false);
 }catch(e){toast('Gagal menghitung ulang: '+e.message);}
}
async function refreshRoutes(dayIndex=null,notify=true){
 if(!st.plan||st.readOnly)return;
 if(st.routingBusy){if(notify)toast('Perhitungan rute sedang berjalan.');return;}
 st.routingBusy=true;const epoch=++st.routingEpoch;
 const progress=$('routingProgress');progress.hidden=false;
 progress.textContent=dayIndex===null?'⏳ Mengambil rute hotel–wisata–hotel untuk semua hari…':'⏳ Menghitung ulang rute hari '+(dayIndex+1)+'…';
 for(const id of ['routeBtn','allRoutesBtn'])$(id).disabled=true;
 try{
  const result=await api('/api/routes/refresh',{config:readCfg(),itinerary:st.plan.itinerary,weather:st.weather,day:dayIndex});
  if(epoch!==st.routingEpoch)return;
  st.routeCache={...(result.plan.config.route_cache||{})};
  st.plan=result.plan;showPlan(result.plan);
  const r=result.routing,src=Object.entries(r.sources).map(([k,v])=>legSourceLabel(k)+': '+v+' segmen').join(' · ');
  const detail=[`${r.updated} rute diperbarui`,src,...r.notices].filter(Boolean).join(' · ');
  $('routeInfo').hidden=false;$('routeInfo').textContent=detail;
  progress.textContent=r.updated?`✓ ${r.updated} rute diperbarui. Jadwal dan budget sudah dihitung ulang.`:'ℹ Tidak ada rute baru; cek koordinat dan internet.';
  if(notify)toast(detail||'Rute diperbarui.');
 }catch(e){progress.textContent='⚠ Gagal mengambil rute: '+e.message+'; jadwal tetap memakai estimasi jarak atau data sebelumnya.';if(notify)toast(e.message);}
 finally{st.routingBusy=false;for(const id of ['routeBtn','allRoutesBtn'])$(id).disabled=false;}
}
function openPlace(day,index){st.selection={day,index};const slot=st.plan.itinerary[day].slots[index];$('placeKind').value=slot.kind;$('filterPlaces').value='';$('manualDetails').open=false;$('placeDialogTitle').textContent='Pilih '+(slot.kind==='kuliner'?'kuliner':'wisata')+' untuk hari ke-'+(day+1);renderPlaceList();openDialog('placeDialog');}
function renderPlaceList(){const query=$('filterPlaces').value.trim().toLocaleLowerCase(),kind=$('placeKind').value;const matches=st.places.filter(p=>p.kind===kind&&(!query||[p.name,p.area,p.theme].some(t=>String(t||'').toLocaleLowerCase().includes(query))));st.modalPlaces=matches.slice(0,120);$('placesCount').textContent=matches.length+' hasil';$('placeResults').innerHTML=st.modalPlaces.length?st.modalPlaces.map((p,i)=>`<div class="place-option"><div><strong>${safe(p.name)}</strong><small>${safe(p.area||st.plan?.config.city||'')} · ${safe(p.theme||kind)}${p.opening_hours?' · '+safe(p.opening_hours):''}</small><small>${safe(p.source||'Lokasi pilihan')} · Harga ilustrasi</small></div><div style="text-align:right"><div class="price">${money(p.price)}</div><button data-index="${i}">Pilih ＋</button></div></div>`).join(''):'<div class="empty-list">Belum ada hasil. Gunakan “Cari di peta” untuk nama tempat lain, atau tambah manual.</div>';$('placeResults').querySelectorAll('button[data-index]').forEach(b=>b.addEventListener('click',()=>choosePlace(st.modalPlaces[Number(b.dataset.index)])));}
async function searchOsm(){const q=$('filterPlaces').value.trim();if(q.length<2){toast('Ketik nama tempat lalu pilih Cari di peta.');return;}const btn=$('searchOsmBtn');setBusy(btn,true,'Mencari…');try{const data=await api('/api/places/search?q='+encodeURIComponent(q)+(st.location?'&lat='+st.location.lat+'&lon='+st.location.lon:''));const known=new Set(st.places.map(p=>p.id));st.places.push(...data.places.filter(p=>!known.has(p.id)));renderPlaceList();toast(data.places.length+' tempat dari OpenStreetMap ditemukan.');}catch(e){toast(e.message+' Kamu bisa tambah manual atau cari di Google Maps.');}finally{setBusy(btn,false);}}
async function choosePlace(place){if(!st.selection||st.readOnly)return;const {day,index}=st.selection;st.plan.itinerary[day].slots[index].kind=place.kind;st.plan.itinerary[day].slots[index].item=JSON.parse(JSON.stringify(place));closeDialog('placeDialog');await recalc();toast('Pilihan tempat diperbarui dan biaya dihitung ulang.');}

async function fixPlaceCoordinate(day,index){
 if(st.readOnly)return;
 const original=st.plan?.itinerary?.[day]?.slots?.[index]?.item;
 if(!original)return;
 const query=window.prompt('Cari koordinat lokasi (nama tempat + kota). Pilih hasil yang benar setelah pencarian:',original.name+' '+(st.plan?.config?.city||''));
 if(query===null||query.trim().length<2)return;
 try{
  const results=await api('/api/places/search?q='+encodeURIComponent(query.trim())+(st.location?'&lat='+st.location.lat+'&lon='+st.location.lon:''));
  if(!results.places.length)return toast('Lokasi belum ditemukan di OpenStreetMap. Coba nama lebih spesifik atau masukkan koordinat dengan Ganti Tempat.');
  const options=results.places.slice(0,5);
  const choices=options.map((p,i)=>(i+1)+'. '+p.name+' — '+(p.area||'')+' ('+p.lat.toFixed(5)+', '+p.lon.toFixed(5)+')').join('\n');
  const chosen=window.prompt('Pilih nomor hasil sesuai lokasi (1-'+options.length+'):\n'+choices,'1');
  if(chosen===null)return;
  const position=Number(chosen)-1;
  if(!Number.isInteger(position)||position<0||position>=options.length)return toast('Nomor lokasi tidak valid.');
  const found=options[position];
  original.lat=found.lat;original.lon=found.lon;original.area=found.area||original.area;
  original.source=original.source+' · koordinat diverifikasi via OSM';
  const known=st.places.find(p=>p.id===original.id);
  if(known){known.lat=found.lat;known.lon=found.lon;known.area=original.area;}
  st.routeCache={};
  await recalc();toast('Koordinat diperbarui. Segmen rute akan dihitung ulang bila online.');
 }catch(e){toast('Gagal mencari koordinat: '+e.message);}
}

function openPrice(day,index){const p=st.plan.itinerary[day].slots[index].item;if(!p)return;st.selection={day,index};$('pricePlaceName').textContent=p.name;$('newPrice').value=p.price;$('newDuration').value=p.duration||80;openDialog('priceDialog');}
async function addNewSlot(){if(st.readOnly){toast('Rencana berbagi tidak dapat diedit.');return;}const day=st.plan.itinerary[st.day];if(day.slots.length>=8){toast('Maksimum 8 aktivitas per hari.');return;}const idx=day.slots.length;day.slots.push({id:'extra-'+Date.now(),kind:'wisata',item:null});openPlace(st.day,idx);}

let leafletPromise=null;
async function loadLeaflet(){if(window.L)return; if(leafletPromise)return leafletPromise;leafletPromise=new Promise((resolve,reject)=>{const link=document.createElement('link');link.rel='stylesheet';link.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.append(link);const script=document.createElement('script');script.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';script.onload=resolve;script.onerror=()=>reject(Error('Library peta tidak dapat dimuat.'));document.body.append(script);});return leafletPromise;}
async function showMap(){if(!$('map').hidden){$('map').hidden=true;$('mapPlaceholder').hidden=false;$('mapBtn').textContent='🗺 Tampilkan peta';return;}$('map').hidden=false;$('mapPlaceholder').hidden=true;$('mapBtn').textContent='✕ Sembunyikan peta';try{await loadLeaflet();if(!st.map){st.map=L.map('map',{scrollWheelZoom:false}).setView([st.location?.lat??-7.7956,st.location?.lon??110.3695],11);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(st.map);}renderMapIfShown();setTimeout(()=>st.map?.invalidateSize(),50);}catch(e){$('map').hidden=true;$('mapPlaceholder').hidden=false;toast(e.message);}}
let markerGroup=null;
function renderMapIfShown(){if(!st.map||!st.plan||$('map').hidden)return;if(markerGroup){markerGroup.remove();markerGroup=null;}if(st.mapRoute){st.mapRoute.remove();st.mapRoute=null;}markerGroup=L.featureGroup().addTo(st.map);
 const base=st.plan.config;
 if(base.base_lat!=null&&base.base_lon!=null)L.marker([base.base_lat,base.base_lon]).addTo(markerGroup).bindPopup('🏨 Hotel: '+safe(base.base_name));
 else if(base.use_city_center_as_base&&base.city_lat!=null)L.circleMarker([base.city_lat,base.city_lon],{radius:9,color:'#bd7b2b'}).addTo(markerGroup).bindPopup('📍 Perkiraan pusat kota (BUKAN hotel)');
 if(base.return_hub_lat!=null&&base.return_hub_lon!=null)L.marker([base.return_hub_lat,base.return_hub_lon]).addTo(markerGroup).bindPopup('🚉 '+safe(base.return_hub_name));
 for(const day of st.plan.itinerary){day.slots.forEach((slot,i)=>{const p=slot.item;if(slot.status==='tidak_terjadwal'||p?.lat==null||p?.lon==null)return;const marker=L.marker([p.lat,p.lon]).addTo(markerGroup);const title=document.createElement('div');const strong=document.createElement('strong');strong.textContent='Hari '+day.day+' · '+p.name;const sub=document.createElement('div');sub.textContent=p.kind+' · '+money(p.price)+'/orang (estimasi)';title.append(strong,sub);marker.bindPopup(title);});}if(markerGroup.getLayers().length)st.map.fitBounds(markerGroup.getBounds().pad(.19),{maxZoom:13});else toast('Lokasi dari katalog offline belum memiliki koordinat. Cari tempat secara dinamis atau tambahkan koordinat manual.');}
async function routeDay(){return refreshRoutes(st.day,true);}

async function findHotelNearby(){
 if(!st.location){toast('Pilih kota terlebih dahulu melalui tombol Cari kota.');return;}
 const btn=$('searchHotelNearby');setBusy(btn,true,'Mencari hotel…');
 try{const data=await api('/api/hotels?lat='+st.location.lat+'&lon='+st.location.lon+'&radius=10000');renderHotelHits(data.hotels||[]);}
 catch(e){toast('Pencarian hotel gagal: '+e.message+' Masukkan koordinat manual bila perlu.');}
 finally{setBusy(btn,false);}
}
async function findHotelByName(){
 const name=$('hotelQuery').value.trim();if(name.length<2){toast('Tulis nama hotel atau kawasan minimal 2 karakter.');return;}
 const btn=$('searchHotelName');setBusy(btn,true,'Mencari…');
 try{const query=name+(!name.toLowerCase().includes(($('destination').value||'').toLowerCase())?' '+$('destination').value:'');
 const data=await api('/api/hotels/search?q='+encodeURIComponent(query)+(st.location?'&lat='+st.location.lat+'&lon='+st.location.lon:''));renderHotelHits(data.hotels||[]);}
 catch(e){toast('Pencarian lokasi gagal: '+e.message+' Silakan masukkan koordinat manual.');}
 finally{setBusy(btn,false);}
}
function renderHotelHits(results){
 st.hotelHits=results.slice(0,90);
 $('hotelResults').innerHTML=st.hotelHits.length?st.hotelHits.map((h,i)=>`<div class="place-option"><div><strong>${safe(h.name)}</strong><small>${safe(h.area||'Area sekitar kota')} · ${safe(h.type)}</small><small>${safe(h.source)} · lokasi saja, bukan harga hotel</small></div><button class="btn btn-light" data-hotel="${i}">Pilih lokasi</button></div>`).join(''):'<div class="empty-list">Belum ada hotel/kawasan ditemukan. Coba kata kunci lain atau masukkan koordinat sendiri.</div>';
 $('hotelResults').querySelectorAll('[data-hotel]').forEach(b=>b.addEventListener('click',async()=>{
  const hotel=st.hotelHits[Number(b.dataset.hotel)];$('hotelName').value=hotel.name;$('hotelArea').value=hotel.area||$('destination').value;
  $('hotelLat').value=hotel.lat;$('hotelLon').value=hotel.lon;closeDialog('hotelDialog');
  if(st.plan&&!st.readOnly)await recalc();toast('Lokasi menginap dipilih; jarak menuju dan dari wisata dapat dihitung.');
 }));
}

async function saveTrip(){if(!st.plan){toast('Buat rencana perjalanan terlebih dahulu.');return;}if(st.readOnly){toast('Link ini hanya untuk melihat. Buat sendiri untuk menyimpan.');return;}try{const title=st.plan.config.city+' · '+fmtDate(st.plan.config.start_date);const r=await api('/api/trips',{plan:st.plan,places:st.places,title,id:st.tripId});st.tripId=r.id;toast('Rencana berhasil disimpan di server. Cadangan tersimpan di browser.');}catch(e){toast('Simpan server gagal: '+e.message+' Cadangan browser tetap tersedia.');}}
async function showTrips(){openDialog('tripsDialog');$('savedTripList').innerHTML='<p class="empty-list">Memuat rencana…</p>';try{const r=await api('/api/trips');$('savedTripList').innerHTML=r.trips.length?r.trips.map(t=>`<div class="saved-trip"><div><strong>${safe(t.title)}</strong><small>Diperbarui ${safe(new Date(t.updated).toLocaleString('id-ID'))}</small></div><div><button class="btn btn-light" data-open="${safe(t.id)}">Buka</button> <button class="btn btn-light" data-delete="${safe(t.id)}">Hapus</button></div></div>`).join(''):'<p class="empty-list">Belum ada rencana tersimpan di server. Kamu bisa pulihkan cadangan browser atau impor JSON.</p>';$('savedTripList').querySelectorAll('[data-open]').forEach(b=>b.addEventListener('click',async()=>{try{const t=await api('/api/trips/'+encodeURIComponent(b.dataset.open));loadPlan(t.plan);st.tripId=t.id;closeDialog('tripsDialog');toast('Rencana berhasil dibuka.');}catch(e){toast(e.message);}}));$('savedTripList').querySelectorAll('[data-delete]').forEach(b=>b.addEventListener('click',async()=>{if(!confirm('Hapus rencana ini dari server?'))return;try{await api('/api/trips/'+encodeURIComponent(b.dataset.delete),undefined,'DELETE');if(st.tripId===b.dataset.delete)st.tripId=null;showTrips();toast('Rencana dihapus.');}catch(e){toast(e.message);}}));}catch(e){$('savedTripList').innerHTML='<p class="empty-list">Server tidak tersedia. Kamu masih bisa memulihkan cadangan browser.</p>';}}
function loadPlan(plan){st.readOnly=false;st.shareId=null;st.shared=null;st.tripId=null;st.places=Array.isArray(plan._catalog)?plan._catalog:plan.itinerary.flatMap(d=>d.slots.map(s=>s.item).filter(Boolean));st.day=0;fillCfg(plan.config);st.weather=plan.weather||{days:[]};showPlan(plan);notice('Rencana dibuka. Lokasi dan harga bisa diedit; gunakan Cari untuk mengambil rekomendasi baru.');}
async function loadBackup(){try{const saved=JSON.parse(localStorage.getItem('jalanyuk-local-backup')||'null');if(!saved?.plan?.config)throw Error('Cadangan browser belum ada.');if(saved.plan.summary){loadPlan(saved.plan);}else{
 const checked=await api('/api/recalculate',{config:saved.plan.config,itinerary:saved.plan.itinerary,weather:saved.weather||{days:[]}});loadPlan(checked);
 }st.places=saved.places||[];st.weather=saved.weather||{days:[]};closeDialog('tripsDialog');toast('Cadangan browser dipulihkan.');}catch(e){toast(e.message);}}
function downloadPlan(){if(!st.plan){toast('Buat itinerary terlebih dahulu.');return;}const data={format:'jalanyuk-2.5',exported_at:new Date().toISOString(),plan:safeTripSnapshot(st.plan),places:st.places};const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='jalanyuk-'+st.plan.config.city.toLowerCase().replace(/[^a-z0-9]+/g,'-')+'-'+st.plan.config.start_date+'.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);toast('File itinerary berhasil disiapkan.');}
async function importJSON(file){if(!file)return;try{if(file.size>1_000_000)throw Error('File JSON maksimal 1 MB.');const obj=JSON.parse(await file.text());const plan=obj.plan||obj;if(!plan.config||!Array.isArray(plan.itinerary))throw Error('Format itinerary tidak valid.');const checked=await api('/api/recalculate',{config:plan.config,itinerary:plan.itinerary,weather:plan.weather||{days:[]}});loadPlan(checked);st.places=Array.isArray(obj.places)?obj.places:[];closeDialog('tripsDialog');toast('Rencana berhasil diimpor dan diverifikasi ulang oleh Python.');}catch(e){toast('Impor gagal: '+e.message);}finally{$('fileImport').value='';}}
function printPlan(){if(!st.plan){toast('Susun itinerary dulu.');return;}
 let target=$('printOutput');if(!target){target=document.createElement('div');target.id='printOutput';target.className='print-sheet';$('planView').appendChild(target);}
 const p=st.plan,t=p.summary.travel_timeline||{};
 target.innerHTML=`<h1>JalanYuk — ${safe(p.config.city)}</h1><p>${p.summary.persons} wisatawan · ${p.config.days} hari wisata</p>
 <p><b>Berangkat:</b> ${safe(t.berangkat||'—')}<br><b>Tiba kota wisata:</b> ${safe(t.tiba_tujuan||'—')}<br><b>Mulai kegiatan:</b> ${safe(t.mulai_wisata||'—')}<br><b>Berangkat pulang:</b> ${safe(t.berangkat_pulang||'—')}<br><b>Tiba kota asal:</b> ${safe(t.tiba_rumah||'—')}</p>
 <h2>Estimasi ${money(p.summary.total)} / budget ${money(p.summary.budget)}</h2><p>Hotel/titik awal: ${safe(p.config.base_name)} · ${safe(p.config.hotel_area||'')}. Target pulang hotel per hari tersedia dalam jadwal.</p>${p.itinerary.map(d=>`<section class="day-print"><h2>Hari ${d.day} — ${safe(fmtDate(d.date))}</h2><p>Jam yang tersedia: ${safe(d.window_start)} – ${safe(d.window_end)}</p>${d.slots.map(slot=>`<p>${safe(slot.start||'—')} · <strong>${safe(slot.item?.name||'Belum dipilih')}</strong> · ${money(slot.cost)}${slot.status==='tidak_terjadwal'?' (TIDAK TERJADWAL)':''}${slot.item?.area?' · '+safe(slot.item.area):''}</p>`).join('')}<p>Perjalanan: ${(d.travel_legs||[]).map(l=>safe(l.from)+' → '+safe(l.to)+' ('+(l.minutes==null?'?':l.minutes)+' menit)').join('; ')}</p><p>Target kembali ke hotel: ${safe(d.hotel_return_target||'—')} · Total aktivitas hari ini: ${money(d.cost)}</p></section>`).join('')}
 <hr><h2>Rincian Biaya</h2>${Object.entries(p.summary.breakdown).map(([k,v])=>`<p>${safe(k.replaceAll('_',' '))}: <b>${money(v)}</b></p>`).join('')}<p><small>Semua harga perkiraan, verifikasi tarif operator dan waktu perjalanan aktual.</small></p>`;
 window.print();
}

async function shareTrip(){if(!st.plan){toast('Buat rencana lebih dahulu.');return;}try{if(!st.shareId){const r=await api('/api/shares',{plan:st.plan,title:'Liburan '+st.plan.config.city});st.shareId=r.id;}await openShare(st.shareId);}catch(e){toast('Gagal membagikan rencana: '+e.message);}}
async function openShare(id){$('shareLink').value=location.origin+'/s/'+id;openDialog('shareDialog');await refreshShare();}
async function refreshShare(){if(!st.shareId)return;try{st.shared=await api('/api/shares/'+st.shareId);renderSuggestions();$('syncShareBtn').hidden=!st.shared.owner;}catch(e){toast(e.message);}}
function renderSuggestions(){const s=st.shared?.suggestions||[];$('sharedSuggestions').innerHTML='<h4>Usulan & voting rombongan ('+s.length+')</h4>'+(s.length?s.map(p=>`<div class="suggest-item"><div><strong>${safe(p.name)}</strong><small>${safe(p.kind)} · Hari ${p.day} · ${money(p.price)}/orang</small><small>${safe(p.comment)}</small></div><div><button data-vote="${p.id}">${p.mine?'✓':'♡'} ${p.votes}</button>${st.shared?.owner?` <button data-apply="${p.id}">＋ Terapkan</button>`:''}</div></div>`).join(''):'<p class="small-note">Belum ada usulan. Ajak teman membuka link ini dan menambahkan ide wisata.</p>');$('sharedSuggestions').querySelectorAll('[data-vote]').forEach(b=>b.addEventListener('click',async()=>{try{await api('/api/shares/'+st.shareId+'/vote',{id:Number(b.dataset.vote)});await refreshShare();}catch(e){toast(e.message);}}));$('sharedSuggestions').querySelectorAll('[data-apply]').forEach(b=>b.addEventListener('click',async()=>{const p=s.find(x=>x.id===Number(b.dataset.apply));if(!p||!st.plan)return;const di=p.day-1,day=st.plan.itinerary[di];if(!day||day.slots.length>=8){toast('Hari tersebut penuh atau tidak ada.');return;}const item={id:'proposal-'+p.id,name:p.name,kind:p.kind,price:p.price,duration:p.kind==='kuliner'?55:85,area:'Usulan teman',theme:p.kind==='kuliner'?'Kuliner':'Wisata',lat:null,lon:null,source:'Usulan rombongan (manual)',price_status:'ilustrasi',outdoor:false};day.slots.push({id:'suggest-'+p.id,kind:p.kind,item});closeDialog('shareDialog');await recalc();toast('Usulan diterapkan. Klik Perbarui link untuk menyinkronkan ke rombongan.');}));}
async function sendSuggestion(e){e.preventDefault();if(!st.shareId){toast('Belum ada link berbagi.');return;}try{await api('/api/shares/'+st.shareId+'/suggest',{name:$('suggestName').value.trim(),kind:$('suggestKind').value,price:num('suggestPrice'),day:num('suggestDay'),comment:$('suggestComment').value});$('suggestName').value='';$('suggestComment').value='';toast('Usulan berhasil ditambahkan.');await refreshShare();}catch(e){toast(e.message);}}
async function syncShare(){if(!st.shareId||!st.plan)return;try{await api('/api/shares/'+st.shareId+'/sync',{plan:st.plan,title:'Liburan '+st.plan.config.city});toast('Rencana di link berbagi telah diperbarui.');await refreshShare();}catch(e){toast(e.message);}}
async function loadShareFromURL(){const m=location.pathname.match(/^\/s\/([A-Za-z0-9_-]{16,80})$/);if(!m)return;try{const shared=await api('/api/shares/'+m[1]);st.shareId=m[1];st.shared=shared;st.readOnly=!shared.owner;fillCfg(shared.plan.config);st.weather=shared.plan.weather||{days:[]};st.day=0;showPlan(shared.plan);if(st.readOnly){$('generateBtn').disabled=true;notice('Kamu sedang melihat rencana yang dibagikan. Untuk memberi ide, klik Bagikan lalu isi usulan dan voting.');}else notice('Link berbagi milikmu dibuka. Kamu boleh mengedit dan menyinkronkan perubahan ke rombongan.');}catch(e){notice('Link tidak dapat dibuka: '+e.message,'error');}}
function externalSearch(type){const city=st.plan?.config.city||$('destination').value||'Indonesia';const query=type==='hotel'?'hotel di '+city:'tempat wisata dan kuliner di '+city;const url=type==='hotel'?'https://www.google.com/travel/hotels?q='+encodeURIComponent(city):'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(query);window.open(url,'_blank','noopener,noreferrer');}

// Event binding (tanpa auto-complete ke Nominatim)
function addDays(iso,n){const d=new Date(iso+'T12:00:00');d.setDate(d.getDate()+Number(n));return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
function dateDifference(a,b){return Math.round((new Date(b+'T12:00:00')-new Date(a+'T12:00:00'))/86400000);}
function validateTripInput(c){
 const checkpoints=[`${c.depart_date}T${c.depart_time}`,`${c.destination_arrival_date}T${c.destination_arrival_time}`,
 `${c.start_date}T${c.arrival_time}`,`${c.return_date}T${c.return_time}`,`${c.home_arrival_date}T${c.home_arrival_time}`];
 if(checkpoints.some(t=>t.includes('undefined')||t.endsWith('T')))throw Error('Lengkapi tanggal dan jam pergi, wisata dan pulang.');
 if(checkpoints.some((t,i)=>i&&t<checkpoints[i-1]))throw Error('Waktu perjalanan harus urut: berangkat, tiba tujuan, mulai wisata, berangkat pulang, dan tiba asal.');
 const days=dateDifference(c.start_date,c.return_date)+1;
 if(days<1||days>14)throw Error('Rentang kegiatan wisata harus 1–14 hari.');
 if(c.infants_under_2&&!c.adults&&!c.seniors)throw Error('Bayi di bawah 2 tahun harus didampingi orang dewasa/lansia.');
 if(c.children_age_2>c.children)throw Error('Jumlah anak tepat 2 tahun tidak boleh melebihi total anak ≥2 tahun.');
}
function setReturnFromDays(){if(!$('startDate').value)return;const oldReturn=$('returnDate').value;
 $('returnDate').value=addDays($('startDate').value,num('days')-1);
 if(!$('homeArrivalDate').value||$('homeArrivalDate').value===oldReturn||$('homeArrivalDate').value<$('returnDate').value)$('homeArrivalDate').value=$('returnDate').value;
}
function syncDurationFromReturn(){if(!$('startDate').value||!$('returnDate').value)return;
 const diff=dateDifference($('startDate').value,$('returnDate').value)+1;
 if(diff>=1&&diff<=14)$('days').value=String(diff);
 else toast('Rentang kegiatan harus 1 sampai 14 hari.');
 if($('homeArrivalDate').value<$('returnDate').value)$('homeArrivalDate').value=$('returnDate').value;
}
$('startDate').value=today();$('departDate').value=today();$('destinationArrivalDate').value=today();
$('returnDate').value=addDays(today(),2);$('homeArrivalDate').value=addDays(today(),2);
$('startDate').addEventListener('change',setReturnFromDays);
$('days').addEventListener('change',setReturnFromDays);
$('returnDate').addEventListener('change',syncDurationFromReturn);
$('children').addEventListener('change',()=>{if(num('childrenAge2')>num('children'))$('childrenAge2').value=$('children').value;});
$('findCityBtn').addEventListener('click',searchCity);
$('pickHotelBtn').addEventListener('click',()=>{if(st.readOnly)return toast('Rencana berbagi hanya-baca.');$('hotelQuery').value=$('hotelName').value||$('hotelArea').value||'';openDialog('hotelDialog');});
$('searchHotelNearby').addEventListener('click',findHotelNearby);$('searchHotelName').addEventListener('click',findHotelByName);
$('hotelQuery').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();findHotelByName();}});
$('destination').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();searchCity();}});
$('destination').addEventListener('input',()=>{$('cityMatches').hidden=true;if($('destination').value.trim()!==st.lastCity)st.location=null;});
document.querySelectorAll('[data-city]').forEach(b=>b.addEventListener('click',()=>{$('destination').value=b.dataset.city;st.location=null;st.lastCity='';searchCity();document.querySelector('.settings').scrollIntoView({behavior:'smooth'});}));
$('tripForm').addEventListener('submit',generate);
$('tripsBtn').addEventListener('click',showTrips);
$('saveBtn').addEventListener('click',saveTrip);$('saveTopBtn').addEventListener('click',saveTrip);
$('shareBtn').addEventListener('click',shareTrip);
$('optimizeBtn').addEventListener('click',()=>{if(st.readOnly){toast('Rencana berbagi hanya bisa dibaca.');return;}recalc(true);});
$('budgetOptimizeBtn').addEventListener('click',async()=>{if(!st.plan||st.readOnly)return toast('Buat rencana sendiri dahulu.');const btn=$('budgetOptimizeBtn');setBusy(btn,true,'Menghemat…');try{const optimized=await api('/api/optimize',{config:readCfg(),itinerary:st.plan.itinerary,places:st.places,weather:st.weather});if(optimized.adjustments?.length){st.previousPlan=JSON.parse(JSON.stringify(st.plan));showPlan(optimized);$('undoBtn').hidden=false;toast(optimized.adjustments.length+' tempat diganti, penghematan '+money(optimized.adjustments.reduce((s,c)=>s+c.saved,0))+'.');}else toast('Belum ada alternatif lebih murah yang dapat diterapkan.');}catch(e){toast(e.message);}finally{setBusy(btn,false);}});
$('undoBtn').addEventListener('click',()=>{if(!st.previousPlan)return;const prev=st.previousPlan;st.previousPlan=null;showPlan(prev);$('undoBtn').hidden=true;toast('Perubahan hemat otomatis dibatalkan.');});
$('freeAddBtn').addEventListener('click',addNewSlot);$('addDayPlace').addEventListener('click',addNewSlot);
$('routeBtn').addEventListener('click',routeDay);
$('allRoutesBtn').addEventListener('click',()=>refreshRoutes(null,true));$('mapBtn').addEventListener('click',showMap);
$('downloadBtn').addEventListener('click',downloadPlan);$('printBtn').addEventListener('click',printPlan);
$('googleSearchBtn').addEventListener('click',()=>externalSearch('wisata'));$('hotelSearchBtn').addEventListener('click',()=>externalSearch('hotel'));
$('googlePlaceBtn').addEventListener('click',()=>{const name=$('filterPlaces').value.trim()||$('placeKind').value;const city=st.plan?.config.city||$('destination').value;window.open('https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(name+' '+city),'_blank','noopener,noreferrer');});
$('filterPlaces').addEventListener('input',renderPlaceList);$('placeKind').addEventListener('change',renderPlaceList);$('searchOsmBtn').addEventListener('click',searchOsm);
$('manualForm').addEventListener('submit',async e=>{e.preventDefault();const kind=$('placeKind').value;const lat=$('manualLat').value,lon=$('manualLon').value;const p={id:'custom-'+Date.now(),name:$('manualName').value.trim(),price:num('manualPrice'),duration:num('manualDuration'),kind,area:$('manualArea').value.trim(),theme:kind==='wisata'?'Pilihan pribadi':'Kuliner',lat:lat&&lon?Number(lat):null,lon:lat&&lon?Number(lon):null,source:'Ditambahkan pengguna',price_status:'diisi pengguna',outdoor:false};st.places.push(p);await choosePlace(p);$('manualForm').reset();$('manualDuration').value='80';});
$('priceForm').addEventListener('submit',async e=>{e.preventDefault();const {day,index}=st.selection||{};const p=st.plan?.itinerary?.[day]?.slots?.[index]?.item;if(!p)return;p.price=num('newPrice');p.duration=num('newDuration');p.price_status='diubah pengguna';closeDialog('priceDialog');await recalc();toast('Biaya baru tersimpan dalam perhitungan.');});
document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',()=>closeDialog(b.dataset.close)));
$('importBtn').addEventListener('click',()=>$('fileImport').click());$('fileImport').addEventListener('change',e=>importJSON(e.target.files[0]));$('importLocalBtn').addEventListener('click',loadBackup);
$('copyShareBtn').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('shareLink').value);toast('Link berbagi disalin.');}catch{$('shareLink').select();toast('Salin link yang sudah dipilih secara manual.');}});
$('syncShareBtn').addEventListener('click',syncShare);$('suggestForm').addEventListener('submit',sendSuggestion);
// Mengubah field biaya memperbarui hasil secara real-time (on change). Durasi/tempo perlu generate ulang.
const recalcIds=['budget','adults','children','childrenAge2','infants','seniors','hotelRate','roomCapacity','outboundMode','outboundFare','returnMode','returnFare','carCapacity','trainInfantWithoutSeat','trainAge2WithoutSeat','flightInfantPercent','otherInfantPercent','childActivityPercent','infantActivityPercent','childFoodPercent','infantFoodPercent','age2ActivityPercent','age2FoodPercent','localRate','localChildPercent','localInfantPercent','localAge2Percent','parking','misc','emergency','includeHotel','infantUsesBed','departDate','departTime','destinationArrivalDate','destinationArrivalTime','startDate','arrival','dailyStartTime','returnDate','returnTime','returnBuffer','homeArrivalDate','homeArrivalTime','hotelName','hotelArea','hotelLat','hotelLon','useCityBase','returnHotel',
'includeEvening','nightStart','hotelReturnDefault','lastViaHotel','returnHubName','returnHubLat','returnHubLon',
'routeSafety','unknownLegMinutes','localTravelMode','localCostMode','localPerKm','localBaseLeg','localCapacity','trafficPercent','visitGap','routingProvider','localUtcOffset'];
recalcIds.forEach(id=>$(id).addEventListener('change',()=>{if(st.plan&&!st.readOnly)recalc();}));
['days','pace'].forEach(id=>$(id).addEventListener('change',()=>{if(st.plan)toast('Durasi/tempo berubah. Tekan Buat rencana untuk menyusun ulang seluruh hari.');}));
window.addEventListener('online',()=>toast('Koneksi kembali. Pencarian lokasi live siap digunakan.'));
window.addEventListener('offline',()=>notice('Kamu sedang offline. Cadangan itinerary di browser tetap bisa dibuka, tetapi pencarian online dan cuaca tidak tersedia.'));
if('serviceWorker'in navigator&&(location.protocol==='https:'||location.hostname==='localhost'||location.hostname==='127.0.0.1'))navigator.serviceWorker.register('/sw.js').catch(()=>{});
api('/api/routing/status').then(r=>{
 $('routingServiceStatus').textContent='✓ Tidak memakai Google Routes API. OSRM + buffer konservatif; ORS '+(r.ors_configured?'aktif':'opsional (belum aktif)')+'.';
}).catch(()=>$('routingServiceStatus').textContent='Status penyedia rute belum dapat diperiksa.');
loadShareFromURL();
