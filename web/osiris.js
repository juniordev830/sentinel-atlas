(() => {
  'use strict';
  const natural = document.getElementById('osiris-natural');
  const tactical = document.getElementById('osiris-tactical');
  if (!natural || !tactical) return;
  function setMode(mode) {
    const enabled = mode === 'tactical';
    document.body.classList.toggle('osiris-tactical', enabled);
    natural.setAttribute('aria-pressed', String(!enabled));
    tactical.setAttribute('aria-pressed', String(enabled));
  }
  natural.addEventListener('click', () => setMode('natural'));
  tactical.addEventListener('click', () => setMode('tactical'));
  setMode('natural');
})();