'use strict';
const $ = id => document.getElementById(id);
let initialized = false, lastStamp = '', previousEvents = '', polling = false;
async function api(path, body) {
  const res = await fetch('/api/'+path, body === undefined ? {cache:'no-store'} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (!res.ok) { const data = await res.json().catch(()=>({})); throw Error(typeof data.detail === 'string' ? data.detail : `HTTP ${res.status}`); }
  return res.json();
}
function actionButton(id, active, on, off, a, b) {
  const el=$(id); el.textContent=active?off:on; el.dataset.action=active?b:a; el.classList.toggle('active',active);
}
function loadSettings(s) {
  $('camera').replaceChildren(...[...new Set([s.settings.camera,...s.devices])].map(v=>new Option(v,v)));
  $('camera').value=s.settings.camera; $('resolution').value=`${s.settings.width}x${s.settings.height}`;
  for(const k of ['fps','interval','prompt','max_tokens','temperature','change_threshold']) $(k).value=s.settings[k];
  for(const k of ['save_observations','save_frames','changes_only','mirror','vertical_flip']) $(k).checked=s.settings[k];
}
async function save() {
  const [width,height]=$('resolution').value.split('x').map(Number);
  await api('settings',{camera:$('camera').value,width,height,fps:Number($('fps').value),interval:Number($('interval').value),prompt:$('prompt').value,save_observations:$('save_observations').checked,save_frames:$('save_frames').checked,changes_only:$('changes_only').checked,change_threshold:Number($('change_threshold').value),max_tokens:Number($('max_tokens').value),temperature:Number($('temperature').value),mirror:$('mirror').checked,vertical_flip:$('vertical_flip').checked});
}
function renderEvents(events) {
  const key=JSON.stringify(events); if(key===previousEvents)return; previousEvents=key;
  for(const id of ['events','chat']) {
    const pane=$(id); const opened = new Set([...pane.querySelectorAll('details[open]')].map(d=>d.dataset.key));
    const follow = pane.scrollHeight-pane.scrollTop-pane.clientHeight < 40;
    const oldScroll = pane.scrollTop;
    pane.replaceChildren();
    const items=events.filter(e=>id==='chat'?e.kind==='question':e.kind!=='question');
    for(const e of items) {
      const card=document.createElement('article');card.className='entry';
      const stamp=document.createElement('small');stamp.textContent=`${e.captured} · ${e.seconds} сек.`;card.append(stamp);
      if(e.kind==='question'){const q=document.createElement('div');q.className='question';q.textContent=e.question;card.append(q);}
      if(e.reasoning){const d=document.createElement('details');d.dataset.key=e.captured+e.kind;d.open=opened.has(d.dataset.key);const summary=document.createElement('summary');summary.textContent='Рассуждения';d.append(summary,document.createTextNode(e.reasoning));card.append(d);}
      const a=document.createElement('div');a.textContent=e.answer || (e.pending?'Анализируется…':'');card.append(a);pane.append(card);
    }
    pane.scrollTop=follow?pane.scrollHeight:oldScroll;
  }
}
let focusKey = '', showFocus = false, viewRevision = 0;
function renderFocus(s) {
  const f = s.focus;
  const key = f ? `${f.captured}:${f.state}:${JSON.stringify(f.box)}:${f.refinement}` : '';
  if (key !== focusKey) {
    focusKey = key;
    if (f && f.state === 'found') showFocus = true;
    if (s.tracking) showFocus = false;
    if (!f) showFocus = false;
    if (f && (!s.tracking || showFocus)) $('focus-image').src = '/api/focus/frame?t=' + Date.now();
    else $('focus-image').removeAttribute('src');
  }
  if (s.view_revision !== viewRevision) {
    viewRevision = s.view_revision;
    showFocus = s.requested_view === 'search' && !!f;
    if(showFocus) $('focus-image').src='/api/focus/frame?t='+Date.now();
  }
  const states = {searching:'поиск…',found:'рамка получена (проверьте)',missing:'не найден',invalid:'некорректный ответ',error:'ошибка',limit:'лимит генерации',initializing:'инициализация трекера',tracking:'отслеживается',lost:'потерян — повторный поиск'};
  $('focus-status').textContent = f ? `${f.target} · ${states[f.state]} · ${f.live_box ? ' · px: '+f.live_box.join(', ') : ''}${s.tracking ? ' · потери: '+s.losses+' · повторы: '+s.retries : ''}` : 'Фокус не задан';
  $('focus-view').disabled = !f;
  $('focus-clear').disabled = !f;
  $('emergency-clear').disabled = !f && !s.auto && !s.busy;
  $('trajectory').checked=s.attention.trajectory;
  if (![...$('verify-interval').options].some(o=>Number(o.value)===s.attention.verify_interval)) $('verify-interval').add(new Option(s.attention.verify_interval+' сек.',s.attention.verify_interval));
  $('verify-interval').value=String(s.attention.verify_interval);
  $('find').disabled = !s.camera || !s.model || s.busy || s.auto;
  $('track').disabled = $('find').disabled;
  $('refine').disabled = $('find').disabled || s.tracking || !f?.box;
  if (f?.refinement) $('focus-status').textContent += ' · уточнение: '+(states[f.refinement] || f.refinement);
  if (s.tracking) $('focus-status').textContent += ' · проверок: '+s.verifications+(f?.verification?' · '+f.verification:'');
  $('track').classList.toggle('active',s.tracking);
  $('focus-view').textContent = showFocus ? 'Живое видео' : 'Кадр поиска';
  $('focus-image').hidden = !showFocus || !f;
  $('video').hidden = showFocus && !!f;
  if (showFocus && f) $('live').textContent = 'КАДР ПОИСКА';
}
async function refresh() {
  if(polling)return; polling=true;
  try {
    const s=await api('status'); if(!initialized){loadSettings(s);$('trajectory').checked=s.attention.trajectory;$('verify-interval').value=String(s.attention.verify_interval);initialized=true;}
    actionButton('cam',s.camera_active,'Включить камеру','Выключить камеру','camera-on','camera-off');
    actionButton('model',s.model_active,'Включить модель','Выключить модель','model-on','model-off');
    actionButton('auto',s.auto,'Начать анализ','Остановить анализ','auto-on','auto-off');
    $('auto').disabled=!s.auto&&(!s.camera||!s.model||s.tracking); $('snapshot').disabled=!s.camera||!s.model||s.busy;
    $('question').querySelector('button').disabled=!s.camera||!s.model||s.busy;
    $('live').textContent=s.camera?'LIVE':'OFF';$('placeholder').hidden=s.camera;
    if(s.camera&&!$('video').hasAttribute('src')) $('video').src='/api/stream';
    if(!s.camera)$('video').removeAttribute('src');
    if(s.last_time&&s.last_time!==lastStamp){lastStamp=s.last_time;$('last').src='/api/last?t='+Date.now();$('stamp').textContent=s.last_time;$('last-placeholder').hidden=true;}
    $('status').textContent=`Камера: ${s.camera?'активна':'выключена'}\nМодель: ${s.model?'готова':s.model_active?'загрузка…':'выключена'}\nАвтоанализ: ${s.auto?'включён':'выключен'}\nЗапрос: ${s.busy?`выполняется (${s.elapsed} сек.)`:'ожидание'}\nПоследний анализ: ${s.duration} сек.\nРазница кадров: ${s.change_score}%`;
    $('metrics').textContent=`FPS: ${s.fps}   ·   RAM свободно: ${s.ram} GiB   ·   VRAM занято / всего: ${s.gpu} MiB   ·   Анализ: ${s.busy?s.elapsed:s.duration} сек.`;
    if(s.error)$('error').textContent=s.error;
    renderFocus(s);
    renderEvents(await api('events'));
  }catch(e){$('error').textContent=e.message;}finally{polling=false;}
}
for(const id of ['cam','model','auto','snapshot']) $(id).onclick=async()=>{try{$('error').textContent='';if(['camera-on','auto-on','snapshot'].includes($(id).dataset.action))await save();await api('control/'+$(id).dataset.action,{});await refresh();}catch(e){$('error').textContent=e.message;}};
$('save').onclick=async()=>{try{await save();$('error').textContent='Настройки применены';}catch(e){$('error').textContent=e.message;}};
$('question').onsubmit=async e=>{e.preventDefault();try{const text=$('text').value.trim();if(!text)return;await save();await api('question',{text});$('text').value='';await refresh();}catch(e){$('error').textContent=e.message;}};
for (const id of ['mirror','vertical_flip']) $(id).onchange=async()=>{try{await save();await refresh();}catch(e){$('error').textContent=e.message;}};
$('find').onclick=async()=>{try{const text=$('target').value.trim();if(!text)throw Error('Введите название объекта');await save();await api('focus',{text});await refresh();}catch(e){$('error').textContent=e.message;}};
$('track').onclick=async()=>{try{const text=$('target').value.trim();if(!text)throw Error('Введите название объекта');await save();await api('track',{text});showFocus=false;await refresh();}catch(e){$('error').textContent=e.message;}};
$('emergency-clear').onclick=async()=>{try{await api('control/auto-off',{});await api('focus/clear',{});await refresh();}catch(e){$('error').textContent=e.message;}};
$('focus-clear').onclick=async()=>{try{await api('focus/clear',{});await refresh();}catch(e){$('error').textContent=e.message;}};
$('focus-view').onclick=()=>{showFocus=!showFocus;if(showFocus)$('focus-image').src='/api/focus/frame?t='+Date.now();refresh();};
$('refine').onclick=async()=>{try{await api('focus/refine',{});await refresh();}catch(e){$('error').textContent=e.message;}};
for(const id of ['trajectory','verify-interval']) $(id).onchange=async()=>{try{await api('attention/settings',{trajectory:$('trajectory').checked,verify_interval:Number($('verify-interval').value)});await refresh();}catch(e){$('error').textContent=e.message;}};
$('help').onclick=()=>$('manual').showModal();refresh();setInterval(refresh,1000);

$('text').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!$('question').querySelector('button').disabled)$('question').requestSubmit();}});
