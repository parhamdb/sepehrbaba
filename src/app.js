import { createViewer } from '@playcanvas/supersplat-viewer/viewer';
import { defaultSettings } from '@playcanvas/supersplat-viewer/settings';
import { Quat } from 'playcanvas';
import './style.css';

const $ = (id) => document.getElementById(id);
let viewer;
let loadingTimer;
let ready = false;
const expanded = new URLSearchParams(location.search).get('scene') === 'recovery-71s';
const descriptionUrl = expanded ? './experiments/recovery-71s.json' : './scene.json';
if (expanded) {
  document.title = 'Sepehr Baba · Experimental 71-second scene';
  document.querySelector('.coverage').textContent = 'Experimental · 03:06–04:17';
  $('scope-title').textContent = 'Experimental expanded preview';
  $('scope-description').textContent = 'Recovered views span about 71 seconds of the 12-minute recording. This candidate has missing frames, blur and uncertain geometry; it is not the full recording.';
  $('alternate-scene').href = './';
  $('alternate-scene').textContent = 'Open the accepted 18-second pilot ↗';
}

function fail(message) {
  clearTimeout(loadingTimer);
  ready = false;
  viewer?.destroy();
  viewer = undefined;
  $('loading').hidden = true;
  $('toolbar').hidden = true;
  $('move-pad').hidden = true;
  $('error').hidden = false;
  $('error-message').textContent = message;
  $('retry').focus();
}

function setMode(mode) {
  if (!ready) return;
  viewer.state.cameraMode = mode;
  updateControls(mode);
}

function updateControls(mode = viewer?.state.cameraMode) {
  if (!ready) return;
  $('orbit').setAttribute('aria-pressed', String(mode === 'orbit'));
  $('fly').setAttribute('aria-pressed', String(mode === 'fly'));
  $('move-pad').hidden = mode !== 'fly';
  $('hint').textContent = document.pointerLockElement ? 'Mouse to look · W A S D to move · Esc releases the mouse' : mode === 'fly' ? 'Drag to look · W A S D or arrow buttons to move · Esc releases the mouse' : 'Drag to orbit · Scroll or pinch to zoom';
}

async function enter() {
  $('intro').hidden = true;
  $('error').hidden = true;
  $('loading').hidden = false;
  $('progress').textContent = 'Opening scene…';
  loadingTimer = setTimeout(() => fail('Loading timed out. Check your connection and try again.'), 60000);
  try {
    const response = await fetch(descriptionUrl);
    if (!response.ok) throw new Error('The scene description could not be downloaded.');
    const scene = await response.json();
    document.querySelector('#error a[download]').href = scene.asset;
    const settings = defaultSettings('object');
    settings.background.color = [0.045, 0.058, 0.05];
    settings.cameras = scene.camera ? [{ initial: scene.camera }] : [];
    // Install the transform before the viewer measures its bounds and creates
    // navigation controls. Defer the asset fetch until the child hook is ready.
    let startAsset;
    const contents = scene.orientation ? new Promise(resolve => {
      startAsset = () => resolve(fetch(scene.asset));
    }) : undefined;
    viewer = await createViewer({
      container: $('viewer'), contentUrl: scene.asset, contents, settings,
      renderer: new URLSearchParams(location.search).has('webgl') ? 'webgl' : 'webgpu',
      ui: false, nofx: true, aa: true
    });
    if (scene.orientation) {
      const root = viewer.app.root;
      const orient = (entity) => {
        if (!entity.gsplat) return;
        const correction = new Quat(...scene.orientation.rotation_xyzw);
        entity.setLocalRotation(correction.mul(entity.getLocalRotation()));
        root.off('childinsert', orient);
      };
      root.on('childinsert', orient);
    }
    viewer.events.on('progress:changed', (value) => { $('progress').textContent = `Loading scene · ${Math.round(value)}%`; });
    const loaded = () => {
      if (ready) return;
      clearTimeout(loadingTimer);
      ready = true;
      document.body.classList.add('scene-ready');
      document.body.dataset.sceneLoaded = 'true';
      $('loading').hidden = true;
      $('toolbar').hidden = false;
      viewer.state.gamingControls = false;
      viewer.state.animationPaused = true;
      setMode('orbit');
      viewer.resetCamera();
      $('orbit').focus({ preventScroll: true });
    };
    viewer.events.on('loaded:changed', (value) => { if (value) loaded(); });
    viewer.events.on('cameraMode:changed', updateControls);
    if (viewer.state.loaded) loaded();
    // Read-only visibility for browser verification; no credentials or write API.
    window.sceneViewer = viewer;
    startAsset?.();
  } catch (error) {
    fail(`${error.message || 'Your browser could not open the scene.'} Try a current browser with WebGL or WebGPU enabled.`);
  }
}

$('enter').addEventListener('click', enter);
$('retry').addEventListener('click', () => location.reload());
$('orbit').addEventListener('click', () => setMode('orbit'));
$('fly').addEventListener('click', () => setMode('fly'));
$('reset').addEventListener('click', () => { setMode('orbit'); viewer.resetCamera(); });
$('fullscreen').addEventListener('click', async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch { $('hint').textContent = 'Fullscreen is unavailable in this browser.'; }
});
function showHelp(show) {
  $('help').hidden = !show;
  $('help-button').setAttribute('aria-expanded', String(show));
  if (show) $('close-help').focus();
  else $('help-button').focus();
}
$('help-button').addEventListener('click', () => showHelp($('help').hidden));
$('close-help').addEventListener('click', () => showHelp(false));
document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !$('help').hidden) showHelp(false); });
for (const button of document.querySelectorAll('[data-move]')) {
  button.addEventListener('pointerdown', (event) => {
    if (!ready) return;
    event.preventDefault();
    button.setPointerCapture(event.pointerId);
    viewer.setMoveInput(...button.dataset.move.split(',').map(Number));
  });
  for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(name, () => {
    if (ready) viewer.setMoveInput(0, 0);
  });
}
window.addEventListener('pagehide', () => { clearTimeout(loadingTimer); viewer?.destroy(); });
document.addEventListener('pointerlockchange', () => updateControls());
