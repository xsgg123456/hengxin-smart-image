const $ = id => document.getElementById(id);
const svgNS = 'http://www.w3.org/2000/svg';
const fresh = () => ({ boxes: [], general: '', upload: null, mode: 'direct', history: [], selected: null });
const drafts = { CLI: fresh(), API: fresh() };
let channel = 'CLI', tool = 'draw', zoom = 1, view = { x: 0, y: 0 }, gesture = null, serial = 0;
let compositeUrl = null, reading = false;
let spacePan = false, canvasHovered = false;
const state = () => drafts[channel];
const baseImage = new Image(); baseImage.src = 'assets/result.jpg';
const clone = value => JSON.parse(JSON.stringify(value));
function remember() { state().history.push(clone(state().boxes)); if (state().history.length > 50) state().history.shift(); }
function restoreBoxes(snapshot) {
 const notes = new Map(state().boxes.map(b => [b.id, b.note]));
 state().boxes = snapshot.map(b => ({ ...b, note: notes.has(b.id) ? notes.get(b.id) : b.note }));
}
function error(text = '') { $('error').textContent = text; }
function point(event) { return new DOMPoint(event.clientX, event.clientY).matrixTransform($('canvas').getScreenCTM().inverse()); }
function clamp(n, min = 0, max = 800) { return Math.max(min, Math.min(n, max)); }
function element(name, attrs) { const node = document.createElementNS(svgNS, name); for (const [k,v] of Object.entries(attrs)) node.setAttribute(k, v); return node; }
function drawBoxes() {
 $('boxes').replaceChildren();
 state().boxes.forEach((b,i) => {
  const selected = b.id === state().selected;
  const group = element('g', { 'data-id': b.id });
  if(b.points) group.append(element('path',{d:b.points.map((p,j)=>`${j?'L':'M'} ${p.x} ${p.y}`).join(' '),fill:'none',stroke:'#d66a26','stroke-width':selected?4:3,'stroke-linecap':'round','stroke-linejoin':'round','vector-effect':'non-scaling-stroke'}));
  else group.append(element('rect', { x:b.x,y:b.y,width:b.w,height:b.h,rx:3,fill:selected?'#ed7c221c':'#ed7c220b',stroke:'#d66a26','stroke-width':selected?3:2,'vector-effect':'non-scaling-stroke' }));
  const badge = element('circle',{cx:b.x+13,cy:b.y+13,r:12,fill:'#d66a26'});
  const label = element('text',{x:b.x+13,y:b.y+18,'text-anchor':'middle',fill:'white','font-size':15,'font-family':'Arial'}); label.textContent=i+1;
  group.append(badge,label);
  if(selected && !b.points) group.append(element('rect',{x:b.x+b.w-7,y:b.y+b.h-7,width:14,height:14,fill:'white',stroke:'#d66a26','stroke-width':2,'data-resize':'true',style:'cursor:nwse-resize'}));
  $('boxes').append(group);
 });
 $('count').textContent = `${state().boxes.length} 处`;
 $('selectionCount').textContent = `已标注 ${state().boxes.length} 处 · 演示图片 · 基于 V3`;
 $('undo').disabled = !state().history.length || state().mode !== 'direct';
 $('remove').disabled = !state().selected || state().mode !== 'direct';
 $('clear').disabled = !state().boxes.length || state().mode !== 'direct';
 $('canvasHint').hidden = state().mode !== 'direct' || !!state().boxes.length;
 $('canvasHint').textContent = tool==='pen'?'按住鼠标自由圈注，松开完成一笔':'在图片上按住并拖动，框出需要修改的位置';
 $('boxes').style.display = state().mode === 'direct' ? '' : 'none';
}
function renderNotes() {
 $('notes').replaceChildren(); $('empty').hidden = state().boxes.length > 0;
 state().boxes.forEach((b,i) => {
  const card=document.createElement('div'); card.className='note'+(b.id===state().selected?' selected':'');
  const heading=document.createElement('div'); heading.className='note-title';
  const badge=document.createElement('span'); badge.className='badge'; badge.textContent=i+1;
  const title=document.createElement('strong'); title.textContent=`第 ${i+1} 处${b.points?' · 画笔':''}`;
  const remove=document.createElement('button'); remove.textContent='移除'; remove.setAttribute('aria-label',`移除第${i+1}处`);
  remove.onclick=()=>{remember(); state().boxes=state().boxes.filter(x=>x.id!==b.id); state().selected=null; render();};
  heading.append(badge,title,remove);
  const input=document.createElement('textarea'); input.rows=2; input.maxLength=500; input.value=b.note; input.placeholder='这个位置应该改成什么？'; input.setAttribute('aria-label',`第${i+1}处修改意见`);
  input.oninput=()=>{b.note=input.value;error();};
  input.onfocus=()=>{state().selected=b.id; drawBoxes(); document.querySelectorAll('.note').forEach(n=>n.classList.toggle('selected',n===card));};
  card.append(heading,input); $('notes').append(card);
 });
}
function render() {
 drawBoxes();renderNotes();$('general').value=state().general;
 $('directPanel').hidden=state().mode!=='direct'; $('uploadPanel').hidden=state().mode!=='upload';
 $('direct').classList.toggle('active',state().mode==='direct');$('uploadMode').classList.toggle('active',state().mode==='upload');
 $('uploaded').hidden=!state().upload; $('drop').hidden=!!state().upload;
 if(state().upload) $('uploadPreview').src=state().upload;
 updateGestureUI();
}
function updateGestureUI() {
 const panning=gesture?.type==='pan', moving=panning||spacePan;
 $('stage').style.cursor=panning?'grabbing':moving?'grab':state().mode==='upload'?'default':'crosshair';
 $('gestureHelp').classList.toggle('panning',moving);
 $('gestureHelp').textContent=panning?'正在移动图片 · 松开后直接继续标注':`当前：${tool==='pen'?'画笔圈注':'框选'} · ${zoom>1?'按住图中右上角“拖动图片”移动，无需切换工具':'可直接标注，放大后可用图中手柄移动图片'}`;
 $('panHandle').classList.toggle('dragging',panning);
 $('panHandle').disabled=zoom===1;
 $('panHandleHint').textContent=zoom===1?'先放大图片':panning?'松开继续标注':'按住这里拖动';
}
function editable(target){return target instanceof Element && !!target.closest('textarea,input,select,[contenteditable="true"]');}
$('stage').addEventListener('pointerenter',()=>{canvasHovered=true;});
$('stage').addEventListener('pointerleave',()=>{canvasHovered=false;});
document.addEventListener('keydown',e=>{
 if(e.code!=='Space'||e.isComposing||e.ctrlKey||e.altKey||e.metaKey||editable(e.target)||$('editor').hidden||$('confirmation').open)return;
 if(!canvasHovered&&!$('stage').contains(document.activeElement))return;
 e.preventDefault();spacePan=true;updateGestureUI();
});
document.addEventListener('keyup',e=>{if(e.code==='Space'){spacePan=false;updateGestureUI();}});
function resetInteraction(){spacePan=false;canvasHovered=false;finish(true);updateGestureUI();}
window.addEventListener('blur',resetInteraction);
document.addEventListener('visibilitychange',()=>{if(document.hidden)resetInteraction();});
function updateView() { $('canvas').setAttribute('viewBox',`${view.x} ${view.y} ${800/zoom} ${800/zoom}`);$('scale').textContent=`${Math.round(zoom*100)}%`;updateGestureUI(); }
function setZoom(next) { const previous=800/zoom; zoom=clamp(next,1,4); const size=800/zoom; view.x=clamp(view.x+(previous-size)/2,0,800-size);view.y=clamp(view.y+(previous-size)/2,0,800-size);updateView(); }
function setTool(next) {tool=next;$('draw').classList.toggle('active',tool==='draw');$('pen').classList.toggle('active',tool==='pen');render();}
$('panHandle').addEventListener('pointerdown',e=>{
 if(e.button!==0||reading||gesture||zoom===1)return;
 gesture={type:'pan',p:point(e),pointerId:e.pointerId};
 $('canvas').setPointerCapture(e.pointerId);e.preventDefault();updateGestureUI();
});
$('panHandle').addEventListener('keydown',e=>{
 const directions={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
 if(!directions[e.key]||gesture||reading)return;
 e.preventDefault();const [x,y]=directions[e.key];view.x=clamp(view.x+x*40/zoom,0,800-800/zoom);view.y=clamp(view.y+y*40/zoom,0,800-800/zoom);updateView();
});
$('canvas').addEventListener('pointerdown',e=>{
 if(![0,1].includes(e.button)||reading||gesture)return;
 const temporaryPan=spacePan||e.button===1;
 const p=point(e); if(!temporaryPan&&(p.x<0||p.y<0||p.x>800||p.y>800))return;
 const hit=e.target.closest('[data-id]');
 if(temporaryPan){gesture={type:'pan',p,view:{...view}};}
 else if(state().mode==='direct'){
  remember();
  if(tool==='pen'){const b={id:++serial,x:p.x,y:p.y,w:0,h:0,note:'',points:[{x:p.x,y:p.y}]};state().boxes.push(b);state().selected=b.id;gesture={type:'pen',p,b};}
  else if(hit){const b=state().boxes.find(x=>x.id===Number(hit.dataset.id));state().selected=b.id;gesture={type:e.target.hasAttribute('data-resize')?'resize':'move',p,b,original:clone(b)};}
  else {const b={id:++serial,x:p.x,y:p.y,w:0,h:0,note:''};state().boxes.push(b);state().selected=b.id;gesture={type:'draw',p,b};}
 }else return;
 gesture.pointerId=e.pointerId;
 $('stage').focus({preventScroll:true});$('canvas').setPointerCapture(e.pointerId);e.preventDefault();drawBoxes();updateGestureUI();
});
$('canvas').addEventListener('pointermove',e=>{
 if(!gesture||e.pointerId!==gesture.pointerId)return;const p=point(e),g=gesture;
 if(g.type==='pan'){view.x=clamp(view.x+g.p.x-p.x,0,800-800/zoom);view.y=clamp(view.y+g.p.y-p.y,0,800-800/zoom);updateView();return;}
 const dx=p.x-g.p.x,dy=p.y-g.p.y,b=g.b;
 if(g.type==='pen'){
  const next={x:clamp(p.x),y:clamp(p.y)},last=b.points.at(-1);
  if(Math.hypot(next.x-last.x,next.y-last.y)>=1){b.points.push(next);const right=Math.max(b.x+b.w,next.x),bottom=Math.max(b.y+b.h,next.y);b.x=Math.min(b.x,next.x);b.y=Math.min(b.y,next.y);b.w=right-b.x;b.h=bottom-b.y;}
 }
 if(g.type==='draw'){b.x=Math.min(g.p.x,clamp(p.x));b.y=Math.min(g.p.y,clamp(p.y));b.w=Math.abs(clamp(p.x)-g.p.x);b.h=Math.abs(clamp(p.y)-g.p.y);}
 if(g.type==='move'){b.x=clamp(g.original.x+dx,0,800-b.w);b.y=clamp(g.original.y+dy,0,800-b.h);if(b.points)b.points=g.original.points.map(p=>({x:p.x+b.x-g.original.x,y:p.y+b.y-g.original.y}));}
 if(g.type==='resize'){b.w=clamp(g.original.w+dx,16,800-b.x);b.h=clamp(g.original.h+dy,16,800-b.y);}
 drawBoxes();
});
function finish(cancelled=false){
 if(!gesture)return;
 if(gesture.type!=='pan'&&(cancelled||(gesture.type==='draw'&&(gesture.b.w<16||gesture.b.h<16))||(gesture.type==='pen'&&gesture.b.points.length<2))){restoreBoxes(state().history.pop());state().selected=null;}
 const pointerId=gesture.pointerId;gesture=null;
 if($('canvas').hasPointerCapture(pointerId))$('canvas').releasePointerCapture(pointerId);
 render();
}
$('canvas').addEventListener('pointerup',e=>{if(e.pointerId===gesture?.pointerId)finish();});
$('canvas').addEventListener('pointercancel',e=>{if(e.pointerId===gesture?.pointerId)finish(true);});
$('canvas').addEventListener('lostpointercapture',e=>{if(e.pointerId===gesture?.pointerId)finish(true);});
$('canvas').addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault();});
$('draw').onclick=()=>setTool('draw');$('pen').onclick=()=>setTool('pen');
$('in').onclick=()=>setZoom(zoom+.25);$('out').onclick=()=>setZoom(zoom-.25);
$('fit').onclick=()=>{zoom=1;view={x:0,y:0};updateView();};
$('undo').onclick=()=>{if(state().history.length){restoreBoxes(state().history.pop());state().selected=null;render();}};
$('remove').onclick=()=>{if(state().selected){remember();state().boxes=state().boxes.filter(b=>b.id!==state().selected);state().selected=null;render();}};
$('clear').onclick=()=>{if(confirm('清空所有标注和对应意见？可以通过“撤销”恢复。')){remember();state().boxes=[];state().selected=null;render();}};
$('general').oninput=e=>{state().general=e.target.value;error();};
function mode(next){if(reading)return;state().mode=next;error();render();}
$('direct').onclick=()=>mode('direct');$('uploadMode').onclick=()=>mode('upload');
document.querySelectorAll('[data-channel]').forEach(button=>button.onclick=()=>{
 if(reading)return;finish(true);channel=button.dataset.channel;
 document.querySelectorAll('[data-channel]').forEach(b=>b.classList.toggle('active',b===button));
 $('title').textContent=channel==='API'?'修改这张结果 · 原图 2':'修改第 2 张图片';error();$('fit').click();render();
});
async function upload(files){
 if(reading)return;error();if(files.length!==1){error('每轮请选择一张标注图。');return;}if(state().upload){error('请先移除已有标注图，再替换。');return;}
 const file=files[0];if(!['image/jpeg','image/png','image/webp'].includes(file.type)||!file.size||file.size>10*1024*1024){error('请选择不超过10 MiB的JPG、PNG或WebP图片。');return;}
 reading=true;$('drop').textContent='正在读取图片…';$('submit').disabled=true;
 const url=URL.createObjectURL(file);
 try {const image=new Image();image.src=url;await image.decode();state().upload=url;render();}
 catch{URL.revokeObjectURL(url);error('图片无法读取，请选择有效图片。');}
 finally{reading=false;$('submit').disabled=false;$('drop').textContent='点击选择，或拖拽 / Ctrl+V 粘贴图片（最多1张，10 MiB）';}
}
$('drop').onclick=()=>$('file').click();$('file').onchange=e=>{upload(Array.from(e.target.files));e.target.value='';};
$('drop').ondragover=e=>{e.preventDefault();};$('drop').ondrop=e=>{e.preventDefault();upload(Array.from(e.dataTransfer.files));};
$('drop').onpaste=e=>{const files=Array.from(e.clipboardData.files);if(files.length){e.preventDefault();upload(files);}};
$('removeUpload').onclick=()=>{URL.revokeObjectURL(state().upload);state().upload=null;render();};
function close(){if(reading)return;resetInteraction();$('editor').hidden=true;$('reopen').focus();}
$('close').onclick=close;$('cancel').onclick=close;$('reopen').onclick=()=>{$('editor').hidden=false;$('draw').focus();};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('confirmation').open)close();});
async function preview(){
 error();const s=state();
 if(s.mode==='direct'&&s.boxes.some(b=>!b.note.trim())){error('请为每一处标注填写修改意见。');return;}
 if(!s.general.trim()&&!(s.mode==='direct'?s.boxes.length:s.upload)){error('请框选并填写意见，或填写整体修改要求。');return;}
 $('submit').disabled=true;
 try {
  if(compositeUrl){URL.revokeObjectURL(compositeUrl);compositeUrl=null;}
  if(s.mode==='upload'&&s.upload){$('composite').src=s.upload;}
  else {
   await baseImage.decode();const c=document.createElement('canvas');c.width=800;c.height=800;const ctx=c.getContext('2d');ctx.drawImage(baseImage,0,0,800,800);
   if(s.mode==='direct') s.boxes.forEach((b,i)=>{ctx.strokeStyle='#d66a26';ctx.lineWidth=3;
    if(b.points){ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();b.points.forEach((p,j)=>j?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();}
    else ctx.strokeRect(b.x,b.y,b.w,b.h);
    ctx.fillStyle='#d66a26';ctx.beginPath();ctx.arc(b.x+13,b.y+13,12,0,Math.PI*2);ctx.fill();ctx.fillStyle='white';ctx.font='15px Arial';ctx.textAlign='center';ctx.fillText(String(i+1),b.x+13,b.y+18);});
   const blob=await new Promise(resolve=>c.toBlob(resolve,'image/png'));if(!blob)throw Error('合成图片失败，请重试。');compositeUrl=URL.createObjectURL(blob);$('composite').src=compositeUrl;
  }
  $('summaryTitle').textContent=`${channel==='CLI'?'Codex CLI':'API 换套图'} · 单张修改`;
  const lines=s.mode==='direct'?s.boxes.map((b,i)=>`第 ${i+1} 处：${b.note.trim()}`):s.upload?['使用上传的标注图定位问题。']:[];
  if(s.general.trim())lines.push('整体要求：'+s.general.trim());
  $('summary').textContent=lines.join('\n\n');$('done').textContent='';$('mock').disabled=false;$('confirmation').showModal();
 }catch(e){error(e.message||'生成预览失败，请重试。');}finally{$('submit').disabled=false;}
}
$('submit').onclick=preview;
$('back').onclick=$('return').onclick=()=>$('confirmation').close();
$('mock').onclick=()=>{$('done').textContent='模拟提交成功。正式接入后将生成新版本；本次未上传文件、未调用模型。';$('mock').disabled=true;};
render();updateView();
