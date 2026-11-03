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
  const context = { document, updateRotation() {} };
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

test('mantém o aviso e desativa os controles quando o WebGL falha', () => {
  // O construtor do globo pode substituir todos os filhos do seu recipiente.
  assert.match(html, /<div id="globe"[^>]*><\/div>\s*<div id="globe-fallback"/);
  const fallback = { hidden: true };
  const overview = { textContent: '' };
  const status = { textContent: '' };
  const controls = [{ disabled: false }, { disabled: false }];
  const elements = { 'globe-fallback': fallback, 'overview-globe': overview, 'api-status': status };
  const context = {
    document: {
      querySelector: () => null,
      querySelectorAll: () => controls,
      getElementById: id => elements[id]
    },
    Globe: () => {},
    initializeSentinel() { throw new Error('WebGL indisponível'); },
    setTimeout() { throw new Error('não deve agendar'); },
    clearTimeout() {},
    console: { error() {} }
  };
  const code = snippet('function setGlobeControlsEnabled(enabled)', 'bootSentinel();');
  vm.runInNewContext(code + '\nbootSentinel();', context);
  assert.equal(fallback.hidden, false);
  assert.equal(overview.textContent, 'INDISPONÍVEL');
  assert.match(status.textContent, /GLOBO 3D INDISPONÍVEL/);
  assert.ok(controls.every(control => control.disabled));
});

test('controle de rotação respeita movimento reduzido, aba oculta e modo mapa', () => {
  const rotation = { autoRotate: false };
  const events = {};
  const button = {
    attrs: {},
    setAttribute(name, value) { this.attrs[name] = value; },
    addEventListener(name, handler) { this[name] = handler; }
  };
  const reset = { addEventListener(name, handler) { this[name] = handler; } };
  const body = { classList: classList() };
  const document = {
    hidden: false, body,
    getElementById(id) { return id === 'rotation-toggle' ? button : reset; },
    addEventListener(name, handler) { events[name] = handler; }
  };
  const media = {
    matches: true,
    addEventListener(name, handler) { events.motion = handler; }
  };
  const context = {
    document, motionPreference: media,
    globe: { controls: () => rotation }
  };
  vm.runInNewContext(
    snippet("const rotationToggle = document.getElementById('rotation-toggle');", '// Atualiza bússola'),
    context
  );
  assert.equal(rotation.autoRotate, false, 'movimento reduzido desliga o giro inicialmente');
  assert.equal(button.attrs['aria-pressed'], 'false');
  button.click();
  assert.equal(rotation.autoRotate, true);
  document.hidden = true;
  events.visibilitychange();
  assert.equal(rotation.autoRotate, false);
  document.hidden = false;
  body.classList.add('map-mode');
  events.visibilitychange();
  assert.equal(rotation.autoRotate, false);
  body.classList.remove('map-mode');
  events.visibilitychange();
  assert.equal(rotation.autoRotate, true);
  events.motion({ matches: true });
  assert.equal(rotation.autoRotate, false);
});

test('recentralizar retorna ao globo e fecha o inspetor', () => {
  let mapEnabled = null;
  let camera = null;
  const inspector = { hidden: false };
  const button = { addEventListener(name, handler) { this[name] = handler; } };
  const context = {
    document: { getElementById: id => id === 'reset-camera' ? button : inspector },
    globe: { pointOfView(position, duration) { camera = { position, duration }; } },
    setMapView(value) { mapEnabled = value; }
  };
  vm.runInNewContext(
    snippet('function resetGlobalView()', '// Atualiza bússola'), context
  );
  button.click();
  assert.equal(mapEnabled, false);
  assert.equal(inspector.hidden, true);
  assert.equal(camera.position.altitude, 2.5);
  assert.equal(camera.duration, 900);
});

test('API com lista vazia remove geofences demonstrativas e atualiza busca', async () => {
  let ringCount = -1;
  let badges = 0;
  let searchUpdates = 0;
  const context = {
    loadedGeofences: [{ name: 'Demo' }],
    globe: { ringsData(data) { ringCount = data.length; } },
    buildRingsData: () => [],
    updateBadges() { badges++; },
    applyAssetSearch() { searchUpdates++; },
    fetch: async () => ({ ok: true, json: async () => [] }),
    console
  };
  vm.runInNewContext(
    snippet('async function fetchBackendGeofences()', 'fetchBackendGeofences();'),
    context
  );
  await context.fetchBackendGeofences();
  assert.equal(context.loadedGeofences.length, 0);
  assert.equal(ringCount, 0);
  assert.equal(badges, 1);
  assert.equal(searchUpdates, 1);
});

test('atualização de camada mantém filtro de pesquisa ativo', () => {
  const assets = [{ id: 'original', type: 'earthquake' }];
  let searched = 0;
  let refreshed = 0;
  let globeUpdated = 0;
  const context = {
    assets,
    document: {
      querySelector: () => ({ dataset: { layer: 'earthquake' } }),
      getElementById: () => ({ value: 'Recife' })
    },
    applyAssetSearch() { searched++; },
    updateBadges() { refreshed++; },
    globe: { pointsData() { globeUpdated++; } },
    getFilteredPoints: () => []
  };
  vm.runInNewContext(
    snippet('function replaceAssets(type, incoming)', 'function getFilteredPoints(layer)'),
    context
  );
  context.replaceAssets('earthquake', [{ id: 'new', type: 'earthquake' }]);
  assert.equal(searched, 1);
  assert.equal(globeUpdated, 0);
  assert.equal(refreshed, 1);
  assert.equal(assets[0].id, 'new');
});

test('pesquisa textual respeita a camada visual selecionada', () => {
  const field = { value: 'Recife' };
  const feedback = { textContent: '' };
  const rendered = [];
  const context = {
    assetSearchInput: field, searchFeedback: feedback,
    assets: [
      { id: 'flight', type: 'aircraft', label: 'Avião Recife', lat: -8, lng: -35 },
      { id: 'ship', type: 'ship', label: 'Navio Recife', lat: -8, lng: -35 }
    ],
    loadedGeofences: [{ name: 'Recife', latitude: -8, longitude: -35, radius_meters: 100 }],
    document: { querySelector: () => ({ dataset: { layer: 'aircraft' } }) },
    globe: {
      pointsData(points) { rendered.push(points); },
      pointOfView() {}
    },
    getFilteredPoints() { return []; }
  };
  vm.runInNewContext(
    snippet('function applyAssetSearch()', "assetSearchInput.addEventListener('input', applyAssetSearch);"),
    context
  );
  context.applyAssetSearch();
  assert.equal(rendered.length, 1);
  assert.equal(rendered[0].length, 1);
  assert.equal(rendered[0][0].type, 'aircraft');
  assert.match(feedback.textContent, /1 RESULTADO/);
});

test('modo cinematográfico exibe e oculta controles sem impedir a saída', () => {
  const classes = classList();
  const handlers = {};
  const focusButton = {
    attrs: {},
    setAttribute(name, value) { this.attrs[name] = value; },
    addEventListener(name, handler) { this[name] = handler; }
  };
  const document = {
    body: { classList: classes },
    getElementById(id) {
      assert.equal(id, 'focus-mode');
      return focusButton;
    },
    addEventListener(name, handler) { handlers[name] = handler; }
  };
  const context = { document };
  vm.runInNewContext(
    snippet("const focusModeButton = document.getElementById('focus-mode');",
      '// No celular, o resumo começa recolhido para preservar espaço para o mapa.'),
    context
  );
  assert.equal(focusButton.attrs['aria-pressed'], undefined);
  focusButton.click();
  assert.equal(classes.contains('focus-mode'), true);
  assert.equal(focusButton.attrs['aria-pressed'], 'true');
  assert.match(focusButton.textContent, /Mostrar painel/);
  handlers.keydown({ key: 'Escape' });
  assert.equal(classes.contains('focus-mode'), false);
  assert.equal(focusButton.attrs['aria-pressed'], 'false');
  focusButton.click();
  focusButton.click();
  assert.equal(classes.contains('focus-mode'), false);
});

test('camada tática é decorativa e não intercepta cliques no globo', () => {
  assert.match(html, /<div class="tactical-overlay" aria-hidden="true">/);
  assert.match(html, /\.tactical-overlay\s*\{[^}]*pointer-events:\s*none/s);
  assert.match(html, /body\.map-mode \.tactical-overlay\s*\{\s*display:\s*none;/);
  assert.match(html, /id="focus-mode" aria-pressed="false"/);
  assert.match(html, /@media \(prefers-reduced-motion: reduce\)/);
});

test('perfis de renderização limitam resolução e protegem dispositivos móveis', () => {
  const context = {};
  vm.runInNewContext(
    snippet('function getRenderProfile(', 'function applyRenderQuality()'),
    context
  );
  const profile = context.getRenderProfile;
  const ultra = profile('ultra', 3.25, false, false);
  assert.equal(ultra.mode, 'ultra');
  assert.equal(ultra.pixelRatio, 2, 'Ultra é limitado a 2x mesmo com DPR mais alto');
  assert.equal(ultra.clouds, true);
  assert.ok(ultra.curvature < 3);
  const mobile = profile('auto', 3, true, false);
  assert.equal(mobile.mode, 'eco');
  assert.equal(mobile.pixelRatio, 1);
  assert.equal(mobile.clouds, false);
  assert.equal(profile('auto', 2, false, false).mode, 'balanced');
  assert.equal(profile('auto', 2, false, false, 16, 12).mode, 'ultra');
  assert.equal(profile('auto', 2, false, false, 4, 8).mode, 'balanced');
  assert.equal(profile('auto', 2, true, false, 16, 12).mode, 'eco');
  assert.equal(profile('auto', 2, false, true).mode, 'eco');
  assert.equal(profile('indefinido', 1.25, false, false).mode, 'balanced');
  assert.equal(profile('ultra', -7, false, false).pixelRatio, 1);
});

test('painel oferece qualidade selecionável e modo terrestre diurno por padrão', () => {
  assert.match(html, /<select id="render-quality"/);
  assert.match(html, /<option value="ultra">Ultra/);
  assert.match(html, /<option value="balanced">Equilibrado/);
  assert.match(html, /<option value="eco">Econômico/);
  assert.match(html, /let currentTexture = 'day'/);
  assert.match(html, /new THREE\.DirectionalLight\(/);
  assert.match(html, /globe\.renderer\?\.\(\)/);
  assert.match(html, /new THREE\.SphereGeometry\(globe\.getGlobeRadius\(\) \* 1\.006/);
});

test('perfil reduz nuvens e densidade geométrica sem remover interações de clique', () => {
  const htmlQuality = snippet('function applyRenderQuality()', "renderQualityControl.addEventListener('change', applyRenderQuality);");
  assert.match(htmlQuality, /cloudsMesh\.visible = profile\.clouds/);
  assert.match(html, /function loadClouds\(\)/);
  assert.match(htmlQuality, /if \(profile\.clouds\) loadClouds\(\)/);
  assert.match(htmlQuality, /globe\.pointResolution\?\.\(profile\.points\)/);
  assert.match(htmlQuality, /globe\.globeCurvatureResolution\?\.\(profile\.curvature\)/);
  assert.doesNotMatch(htmlQuality, /enablePointerInteraction\(false\)/);
});

test('Google Places só aceita categorias oficiais e limita área consultada', () => {
  const context = {};
  vm.runInNewContext(
    snippet('const googlePlacesTypes = new Set(', 'function googleMapsLink(uri)'),
    context
  );
  const request = context.buildNearbySearchRequest('hospital', {lat: -5.79, lng: -35.21}, 90000);
  assert.equal(request.locationRestriction.radius, 5000);
  assert.equal(request.locationRestriction.center.lat, -5.79);
  assert.equal(request.locationRestriction.center.lng, -35.21);
  assert.equal(request.includedPrimaryTypes[0], 'hospital');
  assert.equal(request.maxResultCount, 8);
  assert.deepEqual(Array.from(request.fields),
    ['displayName', 'location', 'formattedAddress', 'googleMapsURI']);
  assert.throws(() => context.buildNearbySearchRequest('unknown', {lat: 0, lng: 0}), /Categoria/);
  assert.throws(() => context.buildNearbySearchRequest('hospital', {lat: 99, lng: 0}), /Centro/);
  assert.throws(() => context.buildNearbySearchRequest('hospital', {lat: 0, lng: Infinity}), /Centro/);
});

test('links do Google Maps são HTTPS e não aceitam URLs de terceiros', () => {
  const context = { URL };
  vm.runInNewContext(
    snippet('function googleMapsLink(uri)', 'function clearGooglePlacesResults()'),
    context
  );
  assert.equal(context.googleMapsLink('https://www.google.com/maps/place/ABC'),
    'https://www.google.com/maps/place/ABC');
  assert.equal(context.googleMapsLink('https://maps.google.com/?q=Brasil'),
    'https://maps.google.com/?q=Brasil');
  assert.equal(context.googleMapsLink('javascript:alert(1)'), null);
  assert.equal(context.googleMapsLink('https://google.com.evil.test/'), null);
  assert.equal(context.googleMapsLink('http://www.google.com/maps'), null);
});

test('limpar lugares remove marcadores e invalida buscas antigas', () => {
  let removed = 0;
  let closed = 0;
  const list = { replaceChildren() { this.cleared = true; } };
  const status = { textContent: '' };
  const context = {
    googlePlacesSearchSequence: 3,
    googlePlaceMarkers: [{setMap(value) { assert.equal(value, null); removed++; }}],
    googlePlacesInfoWindow: {close() { closed++; }},
    document: {getElementById(id) {
      return id === 'google-places-results' ? list : status;
    }}
  };
  vm.runInNewContext(
    snippet('function clearGooglePlacesResults()', 'async function searchGooglePlacesNearby()'),
    context
  );
  context.clearGooglePlacesResults();
  assert.equal(context.googlePlacesSearchSequence, 4);
  assert.equal(removed, 1);
  assert.equal(closed, 1);
  assert.equal(context.googlePlaceMarkers.length, 0);
  assert.equal(list.cleared, true);
  assert.match(status.textContent, /Resultados limpos/);
});

test('Google Places exige clique explícito e mantém dados no mapa Google', () => {
  assert.match(html, /<section id="google-places-panel"/);
  assert.match(html, /body\.map-mode \.google-places-panel \{ display: flex; \}/);
  assert.match(html, /id="google-places-search"/);
  assert.match(html, /document\.getElementById\('google-places-search'\)\.addEventListener\('click', searchGooglePlacesNearby\)/);
  assert.match(html, /google\.maps\.importLibrary\('places'\)/);
  assert.match(html, /Place\.searchNearby\(request\)/);
  assert.match(html, /new google\.maps\.TrafficLayer\(\)\.setMap\(googleMap\)/);
  assert.match(html, /mapTypeId: 'hybrid'/);
  assert.doesNotMatch(html, /localStorage\.setItem\(['"]google-places/i);
});

test('painel GeoINT expõe 16 categorias sem consultas automáticas', () => {
  assert.match(html, /id="geoint-panel"[^>]*hidden/);
  assert.match(html, /id="toggle-geoint"/);
  assert.match(html, /id="geoint-uf"/);
  assert.match(html, /id="geoint-source-list"/);
  assert.match(html, /geointCatalog\.length !== 16/);
  assert.match(html, /\/api\/geoint\/layers'/);
  assert.match(html, /queryGeointLayer\(layer, row, button, output\)/);
  assert.match(html, /button\.addEventListener\('click', \(\) => queryGeointLayer/);
  assert.doesNotMatch(html, /setInterval\(queryGeointLayer/);
});

test('fontes GeoINT não transformam conteúdo remoto em HTML executável', () => {
  const code = snippet('async function queryGeointLayer(', 'async function loadGeointCatalog()');
  assert.match(code, /entry\.textContent = String\(item\.title\)/);
  assert.match(code, /output\.replaceChildren\(\)/);
  assert.match(code, /typeof item\.lat === 'number'/);
  assert.match(code, /type: 'geoint-' \+ layer\.id/);
  assert.doesNotMatch(code, /innerHTML/);
  assert.doesNotMatch(code, /eval\(/);
});

test('GeoINT só abre links HTTPS de NASA Worldview', () => {
  const context = { URL };
  vm.runInNewContext(
    snippet('function safeGeointExternalLink(url)', 'async function queryGeointLayer('),
    context
  );
  assert.equal(
    context.safeGeointExternalLink('https://worldview.earthdata.nasa.gov/'),
    'https://worldview.earthdata.nasa.gov/'
  );
  assert.equal(context.safeGeointExternalLink('https://evil.example/map'), null);
  assert.equal(context.safeGeointExternalLink('http://worldview.earthdata.nasa.gov/'), null);
  assert.equal(context.safeGeointExternalLink('javascript:alert(1)'), null);
});
