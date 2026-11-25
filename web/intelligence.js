'use strict';
const MAX_FILES=20, MAX_TOTAL=60*1024*1024, MAX_IMAGE=12*1024*1024, MAX_TEXT=1024*1024;
function classifyFile(file){
  const ext=String(file.name||'').split('.').pop().toLowerCase();
  if(['png','jpg','jpeg','webp'].includes(ext))return 'image';
  if(['txt','md','csv','json'].includes(ext))return 'text';
  return null;
}
function validateFile(file, count, bytes){
  const kind=classifyFile(file);
  if(!kind)return 'Formato não suportado';
  if(!Number.isFinite(file.size)||file.size<=0)return 'Arquivo vazio ou inválido';
  if(count>=MAX_FILES)return 'Limite de arquivos atingido';
  if(bytes+file.size>MAX_TOTAL)return 'Limite total de memória atingido';
  if(file.size>(kind==='image'?MAX_IMAGE:MAX_TEXT))return 'Arquivo excede o limite individual';
  return null;
}
function matchesFile(file,query){
  const q=String(query||'').trim().toLocaleLowerCase('pt-BR');
  return !q||[file.name,file.kind==='text'?file.text:''].some(v=>String(v||'').toLocaleLowerCase('pt-BR').includes(q));
}
function buildReport(files, selections, notes, now=new Date()){
  return {schema:'sentinel-atlas-intelligence/1',createdAt:now.toISOString(),scope:'local; comparação visual não georreferenciada',
    files:files.map(({id,name,kind,size,width,height})=>({id,name,kind,size,...(kind==='image'?{width,height}:{})})),
    selections:{a:selections.a||null,b:selections.b||null,document:selections.document||null},
    notes:String(notes||'').slice(0,4000)};
}
function initIntelligence(doc){
  const el=id=>doc.getElementById(id);
  const files=[], history=[];
  let sequence=0, busy=false;
  const input=el('files'), search=el('search'), imageA=el('image-a'), imageB=el('image-b'), documentSelect=el('document-select');
  const find=id=>files.find(f=>String(f.id)===String(id));
  const totalBytes=()=>files.reduce((n,f)=>n+f.size,0);
  function log(message){
    history.unshift(new Date().toLocaleTimeString('pt-BR')+' · '+message);
    history.splice(50);
    el('history').replaceChildren(...history.map(message=>{const li=doc.createElement('li');li.textContent=message;return li;}));
  }
  function refreshOptions(select,kind){
    const previous=select.value;
    const empty=doc.createElement('option');empty.value='';empty.textContent='Nenhum';
    select.replaceChildren(empty,...files.filter(f=>f.kind===kind).map(f=>{
      const option=doc.createElement('option');option.value=String(f.id);option.textContent=f.name;return option;
    }));
    select.value=find(previous)?.kind===kind?previous:'';
  }
  function renderLibrary(){
    const matching=files.filter(f=>matchesFile(f,search.value));
    el('search-status').textContent=matching.length+' arquivo(s) encontrado(s)';
    el('library').replaceChildren(...matching.map(f=>{
      const li=doc.createElement('li'), info=doc.createElement('div'), name=doc.createElement('div'), meta=doc.createElement('div');
      name.textContent=f.name;meta.className='file-meta';meta.textContent=(f.kind==='image'?'Imagem · '+f.width+' × '+f.height:'Texto')+' · '+Math.ceil(f.size/1024)+' KB';
      info.append(name,meta);const remove=doc.createElement('button');remove.type='button';remove.textContent='Remover';remove.disabled=busy;
      remove.setAttribute('aria-label','Remover '+f.name);remove.addEventListener('click',()=>{
        const index=files.indexOf(f);if(busy||index<0)return;
        files.splice(index,1);if(f.url)URL.revokeObjectURL(f.url);log('Removido: '+f.name);render();
      });li.append(info,remove);return li;
    }));
  }
  function renderComparison(){
    const a=find(imageA.value),b=find(imageB.value);
    for(const [key,f] of [['a',a],['b',b]]){
      const img=el('preview-'+key);img.hidden=!f;el('empty-'+key).hidden=!!f;
      if(f)img.src=f.url;else img.removeAttribute('src');
      el('caption-'+key).textContent=key.toUpperCase()+' · '+(f?f.name+' · '+f.width+' × '+f.height:'sem arquivo');
    }
    const overlay=el('overlay'), opacity=el('opacity');
    overlay.disabled=!(a&&b);if(overlay.disabled)overlay.checked=false;
    const active=overlay.checked;
    el('comparison').classList.toggle('overlay',active);
    opacity.disabled=!active;el('preview-b').style.opacity=active?String(Number(opacity.value)/100):'1';
    el('opacity-value').textContent=opacity.value+'%';
    el('compare-note').textContent='Comparação manual sem alinhamento geográfico ou data de captura verificada.'+(a&&b&&a.width/a.height!==b.width/b.height?' Proporções diferentes; a sobreposição não é espacialmente alinhada.':'');
  }
  function renderDocument(){
    const f=find(documentSelect.value);
    el('document-preview').textContent=f?.kind==='text'?f.text:'Selecione um documento textual importado.';
  }
  function render(){
    refreshOptions(imageA,'image');refreshOptions(imageB,'image');refreshOptions(documentSelect,'text');
    renderLibrary();renderComparison();renderDocument();
    el('file-count').textContent=files.length+' / '+MAX_FILES;
    el('image-count').textContent=String(files.filter(f=>f.kind==='image').length);
    el('text-count').textContent=String(files.filter(f=>f.kind==='text').length);
    el('volume').textContent=(totalBytes()/1048576).toFixed(2)+' MB';
    el('clear').disabled=busy;el('report').disabled=busy;
  }
  async function decodeImage(file){
    const url=URL.createObjectURL(file);
    try{
      const img=new Image();img.src=url;await img.decode();
      if(!img.naturalWidth||!img.naturalHeight||img.naturalWidth*img.naturalHeight>40000000)throw new Error('Dimensões de imagem excedem 40 megapixels');
      return {url,width:img.naturalWidth,height:img.naturalHeight};
    }catch(e){URL.revokeObjectURL(url);throw e;}
  }
  input.addEventListener('change',async()=>{
    if(busy)return;
    const batch=Array.from(input.files||[]).slice(0,MAX_FILES);
    if(!batch.length)return;
    busy=true;input.disabled=true;render();el('progress').max=batch.length;el('progress').value=0;
    let imported=0,failed=0;
    for(const [index,file] of batch.entries()){
      el('progress-text').textContent='Processando '+(index+1)+' de '+batch.length;
      try{
        const error=validateFile(file,files.length,totalBytes());if(error)throw new Error(error);
        const kind=classifyFile(file),entry={id:++sequence,name:file.name,kind,size:file.size};
        if(kind==='image')Object.assign(entry,await decodeImage(file));
        else entry.text=await file.text();
        files.push(entry);imported++;log('Importado: '+entry.name);
      }catch(e){failed++;log('Não importado: '+file.name+' · '+String(e.message||'Falha'));}
      el('progress').value=index+1;render();
    }
    busy=false;input.disabled=false;input.value='';render();
    el('progress-text').textContent=imported+' importado(s), '+failed+' rejeitado(s)';
  });
  search.addEventListener('input',renderLibrary);
  for(const control of [imageA,imageB,el('overlay'),el('opacity')])control.addEventListener('input',renderComparison);
  documentSelect.addEventListener('change',renderDocument);
  el('clear').addEventListener('click',()=>{
    if(busy)return;
    for(const f of files)if(f.url)URL.revokeObjectURL(f.url);
    files.length=0;history.length=0;el('history').replaceChildren();el('notes').value='';search.value='';
    el('progress').max=1;el('progress').value=0;el('progress-text').textContent='Sessão limpa';render();
  });
  el('report').addEventListener('click',()=>{
    const report=buildReport(files,{a:imageA.value,b:imageB.value,document:documentSelect.value},el('notes').value);
    const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
    const link=doc.createElement('a');link.href=url;link.download='atlas-intelligence-relatorio.json';doc.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);log('Relatório local exportado');
  });
  window.addEventListener('pagehide',e=>{if(!e.persisted)for(const f of files)if(f.url)URL.revokeObjectURL(f.url);});
  render();
}
if(typeof module!=='undefined'&&module.exports)module.exports={classifyFile,validateFile,matchesFile,buildReport};
if(typeof document!=='undefined')initIntelligence(document);
