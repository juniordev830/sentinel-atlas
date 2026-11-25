'use strict';
const SOURCE_STATES = Object.freeze({
  ready: 'Pronta para consulta',
  requires_configuration: 'Requer configuração',
  external_view: 'Visualizador externo',
  needs_region: 'Requer região'
});
function normalizeSources(payload) {
  if (!payload || !Array.isArray(payload.layers) || payload.layers.length > 100) throw new Error('Catálogo inválido');
  return payload.layers.filter(item => item && typeof item.id === 'string' && typeof item.name === 'string').map(item => ({
    id: item.id, name: item.name, provider: String(item.provider || 'Não informado'), nature: String(item.data_kind || 'Não informada'),
    state: Object.hasOwn(SOURCE_STATES,item.status) ? item.status : 'unknown'
  }));
}
function summarizeSources(items) {
  return {total:items.length,pending:items.filter(item => item.state === 'requires_configuration').length};
}
function initOperations(doc) {
  const el = id => doc.getElementById(id);
  let sources = [];
  function render() {
    const filter = el('filter').value;
    const items = sources.filter(item => filter === 'all' || item.state === filter);
    el('sources').replaceChildren(...items.map(item => {
      const card=doc.createElement('article'); card.className='source';card.dataset.state=item.state;
      const title=doc.createElement('h3');title.textContent=item.name;
      const provider=doc.createElement('p');provider.textContent='Fonte: '+item.provider;
      const nature=doc.createElement('p');nature.textContent='Natureza: '+item.nature;
      const state=doc.createElement('p');state.className='state';state.textContent=SOURCE_STATES[item.state]||'Estado desconhecido';
      card.append(title,provider,nature,state);return card;
    }));
  }
  async function localJson(path) {
    const response=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(8000)});
    if(!response.ok)throw new Error('Resposta HTTP '+response.status);
    return response.json();
  }
  async function refresh() {
    el('refresh').disabled=true;el('status').textContent='Consultando API local…';
    const results=await Promise.allSettled([localJson('/api/health'),localJson('/api/geoint/layers').then(normalizeSources)]);
    el('api').textContent=results[0].status==='fulfilled'&&results[0].value?.status==='ok'?'Respondendo':'Não confirmada';
    if(results[1].status==='fulfilled'){
      sources=results[1].value;
      const summary=summarizeSources(sources);
      el('total').textContent=String(summary.total);el('pending').textContent=String(summary.pending);
      el('status').textContent='Catálogo local recebido. Disponibilidade externa não verificada.';
    }else{
      sources=[];el('total').textContent='—';el('pending').textContent='—';
      el('status').textContent='Catálogo indisponível ou acesso não autorizado. Nenhum estado externo foi inferido.';
    }
    el('last').textContent=new Date().toLocaleTimeString('pt-BR');render();el('refresh').disabled=false;
  }
  el('filter').addEventListener('change',render);
  el('refresh').addEventListener('click',refresh);
}
if(typeof module!=='undefined'&&module.exports)module.exports={normalizeSources,summarizeSources};
if(typeof document!=='undefined')initOperations(document);