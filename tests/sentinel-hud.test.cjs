const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

const html = readFileSync(join(__dirname, '..', 'web', 'index.html'), 'utf8');

function snippet(start, end) {
  const from = html.indexOf(start);
  const to = html.indexOf(end, from);
  assert.ok(from >= 0 && to > from, 'expected HUD code should be present');
  return html.slice(from, to);
}

function classList(initial = []) {
  const values = new Set(initial);
  return {
    add(value) { values.add(value); },
    remove(value) { values.delete(value); },
    contains(value) { return values.has(value); },
    toggle(value, enabled) { if (enabled) values.add(value); else values.delete(value); }
  };
}

test('troca para o mapa e permite voltar ao globo', () => {
  const body = { classList: classList() };
  const button = { textContent: '', attrs: {}, setAttribute(name, value) { this.attrs[name] = value; } };
  const document = { body, getElementById: () => button };
  const code = snippet('function setMapView(enabled)', "document.getElementById('map-view').addEventListener");
  const context = { document };
  vm.runInNewContext(code + '\nglobalThis.setMapView = setMapView;', context);
  context.setMapView(true);
  assert.equal(body.classList.contains('map-mode'), true);
  assert.equal(button.attrs['aria-pressed'], 'true');
  assert.match(button.textContent, /Voltar ao globo/);
  context.setMapView(false);
  assert.equal(body.classList.contains('map-mode'), false);
  assert.equal(button.attrs['aria-pressed'], 'false');
  assert.match(button.textContent, /Mapa satélite/);
});

test('filtros anunciam qual camada está selecionada', () => {
  function button(layer, active = false) {
    return {
      dataset: { layer }, classList: classList(active ? ['active'] : []), attrs: {},
      setAttribute(name, value) { this.attrs[name] = value; },
      addEventListener(name, callback) { this[name] = callback; }
    };
  }
  const all = button('all', true);
  const aircraft = button('aircraft');
  const feedback = { textContent: '' };
  const document = {
    querySelectorAll: () => [all, aircraft],
    getElementById: () => feedback
  };
  const updates = [];
  const context = { document, assetSearchInput: { value: '' },
    globe: { pointsData(value) { updates.push(value); } },
    getFilteredPoints: layer => layer };
  const code = snippet("document.querySelectorAll('[data-layer]').forEach(button =>", 'async function fetchBackendGeofences()');
  vm.runInNewContext(code, context);
  aircraft.click();
  assert.equal(all.attrs['aria-pressed'], 'false');
  assert.equal(aircraft.attrs['aria-pressed'], 'true');
  assert.equal(aircraft.classList.contains('active'), true);
  assert.deepEqual(updates, ['aircraft']);
});

test('resumo informa se a API respondeu ao health check', async () => {
  const status = { textContent: '' };
  const overview = { textContent: '', classList: classList() };
  const document = { getElementById: id => id === 'api-status' ? status : overview };
  let online = true;
  const fetch = async () => {
    if (!online) throw new Error('offline');
    return { ok: true, json: async () => ({ timestamp: 1000 }) };
  };
  const context = { document, fetch, Date };
  const code = snippet('async function refreshApiStatus()', 'refreshApiStatus();');
  vm.runInNewContext(code + '\nglobalThis.refreshApiStatus = refreshApiStatus;', context);
  await context.refreshApiStatus();
  assert.equal(overview.textContent, 'ON');
  assert.equal(overview.classList.contains('green'), true);
  online = false;
  await context.refreshApiStatus();
  assert.equal(overview.textContent, 'OFF');
  assert.equal(overview.classList.contains('green'), false);
  assert.match(status.textContent, /API não conectada/);
});

test('aguarda a biblioteca gráfica carregar e inicializa apenas uma vez', () => {
  let load;
  let timeout;
  let starts = 0;
  let fallbacks = 0;
  const fallback = { hidden: false };
  const overview = { textContent: '' };
  const context = {
    document: {
      querySelector: () => ({ addEventListener(name, callback) { load = callback; } }),
      getElementById: id => id === 'globe-fallback' ? fallback : overview
    },
    setTimeout(callback) { timeout = callback; return 1; },
    clearTimeout() {},
    initializeSentinel() { starts++; },
    setGlobeControlsEnabled() {},
    showGlobeFallback() { fallbacks++; },
    console
  };
  const code = snippet('function bootSentinel()', 'bootSentinel();');
  vm.runInNewContext(code + '\nglobalThis.bootSentinel = bootSentinel;', context);
  context.bootSentinel();
  assert.equal(starts, 0);
  context.Globe = () => {};
  load();
  load();
  timeout();
  assert.equal(starts, 1);
  assert.equal(fallback.hidden, true);
  assert.equal(overview.textContent, 'ATIVO');
  assert.equal(fallbacks, 0);
});

test('informa indisponibilidade quando a biblioteca gráfica não carrega', () => {
  let timeout;
  let fallbacks = 0;
  const context = {
    document: { querySelector: () => null },
    setTimeout(callback) { timeout = callback; return 1; },
    clearTimeout() {},
    showGlobeFallback() { fallbacks++; },
    console
  };
  const code = snippet('function bootSentinel()', 'bootSentinel();');
  vm.runInNewContext(code + '\nglobalThis.bootSentinel = bootSentinel;', context);
  context.bootSentinel();
  timeout();
  assert.equal(fallbacks, 1);
});
