import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { MTLLoader } from 'three/addons/loaders/MTLLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { ColladaLoader } from 'three/addons/loaders/ColladaLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';

// ── バージョン・バックエンド URL 取得 ─────────────────────

let backendUrl = '';

fetch('/api/version').then(r => r.json())
  .then(d => { document.getElementById('version').textContent = 'v' + d.version; })
  .catch(() => {});

fetch('/api/config').then(r => r.json())
  .then(d => { backendUrl = d.backendUrl || ''; })
  .catch(() => {});

// ── DOM ──────────────────────────────────────────────────

const dropzone   = document.getElementById('dropzone');
const fileInput  = document.getElementById('fileInput');
const fileListEl = document.getElementById('fileList');
const convertBtn = document.getElementById('convertBtn');
const statusEl   = document.getElementById('status');
const previewWrap = document.getElementById('previewWrap');
const canvas     = document.getElementById('preview');

// ── Three.js セットアップ ─────────────────────────────────

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xeeeeee);

const camera = new THREE.PerspectiveCamera(45, 1, 0.001, 100000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;

scene.add(new THREE.AmbientLight(0xffffff, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 2.0);
sun.position.set(5, 10, 7);
scene.add(sun);
const fill = new THREE.DirectionalLight(0xffffff, 0.5);
fill.position.set(-5, 2, -7);
scene.add(fill);

new ResizeObserver(() => {
  const w = previewWrap.clientWidth;
  const h = previewWrap.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}).observe(previewWrap);

(function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();

// ── カメラフィット ────────────────────────────────────────

function fitCamera(obj) {
  const box = new THREE.Box3().setFromObject(obj);
  const size = box.getSize(new THREE.Vector3()).length();
  const center = box.getCenter(new THREE.Vector3());
  camera.near = size / 100;
  camera.far  = size * 100;
  camera.updateProjectionMatrix();
  camera.position.copy(center).add(new THREE.Vector3(0, size * 0.3, size * 1.5));
  controls.target.copy(center);
  controls.update();
}

// ── 状態 ────────────────────────────────────────────────

let loadedObject = null;
let selectedFiles = [];

const MAIN_EXTS = new Set(['obj', 'fbx', 'dae', 'gltf', 'glb']);

function ext(file) { return file.name.split('.').pop().toLowerCase(); }

function detectFormat(files) {
  for (const fmt of ['fbx', 'obj', 'dae', 'glb', 'gltf']) {
    if (files.some(f => ext(f) === fmt)) return fmt;
  }
  return null;
}

function setStatus(html) { statusEl.innerHTML = html; }

// ── ドロップゾーン ────────────────────────────────────────

dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => { e.preventDefault(); dropzone.classList.remove('drag-over'); handleFiles(e.dataTransfer.files); });
dropzone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => handleFiles(fileInput.files));

async function handleFiles(raw) {
  selectedFiles = Array.from(raw);
  renderFileList();
  convertBtn.disabled = true;
  previewWrap.hidden = true;
  setStatus('');

  const fmt = detectFormat(selectedFiles);
  if (!fmt) {
    setStatus('<span class="error">対応形式: OBJ · FBX · DAE · GLTF · GLB</span>');
    return;
  }

  setStatus('<span class="loading"><span class="spinner"></span>読み込み中...</span>');
  try {
    const obj = await loadModel(selectedFiles, fmt);
    if (loadedObject) scene.remove(loadedObject);
    scene.add(obj);
    loadedObject = obj;
    fitCamera(obj);
    previewWrap.hidden = false;
    convertBtn.disabled = false;
    setStatus(`<span class="success">✓ ${fmt.toUpperCase()} を読み込みました</span>`);
  } catch (e) {
    setStatus(`<span class="error">読み込みエラー: ${e.message}</span>`);
  }
}

function renderFileList() {
  fileListEl.innerHTML = selectedFiles.map(f => {
    const e = ext(f);
    const cls = MAIN_EXTS.has(e) ? 'ext ext-main' : 'ext';
    return `<div class="file-item"><span class="${cls}">${e}</span>${f.name}</div>`;
  }).join('');
}

// ── LoadingManager（ローカルファイルをテクスチャとして解決）────

function makeManager(files) {
  const map = {};
  const urls = [];
  for (const f of files) {
    const u = URL.createObjectURL(f);
    map[f.name.toLowerCase()] = u;
    urls.push(u);
  }
  const mgr = new THREE.LoadingManager();
  mgr.setURLModifier(url => {
    const name = decodeURIComponent(url.split('/').pop().split('?')[0]).toLowerCase();
    return map[name] ?? url;
  });
  mgr._revoke = () => urls.forEach(u => URL.revokeObjectURL(u));
  return mgr;
}

// ── フォーマット別ローダー ────────────────────────────────

async function loadModel(files, fmt) {
  const mgr = makeManager(files);
  try {
    if (fmt === 'obj') return await loadOBJ(files, mgr);
    if (fmt === 'fbx') return await loadFBX(files, mgr);
    if (fmt === 'dae') return await loadDAE(files, mgr);
    if (fmt === 'glb' || fmt === 'gltf') return await loadGLTF(files, mgr);
  } finally {
    mgr._revoke();
  }
}

async function loadOBJ(files, mgr) {
  const objFile = files.find(f => ext(f) === 'obj');
  const mtlFile = files.find(f => ext(f) === 'mtl');
  const objUrl  = URL.createObjectURL(objFile);

  let object;
  if (mtlFile) {
    const mtlUrl = URL.createObjectURL(mtlFile);
    const mats = await new Promise((ok, ng) => new MTLLoader(mgr).load(mtlUrl, ok, undefined, ng));
    mats.preload();
    const loader = new OBJLoader(mgr);
    loader.setMaterials(mats);
    object = await new Promise((ok, ng) => loader.load(objUrl, ok, undefined, ng));
    URL.revokeObjectURL(mtlUrl);
  } else {
    object = await new Promise((ok, ng) => new OBJLoader(mgr).load(objUrl, ok, undefined, ng));
  }
  URL.revokeObjectURL(objUrl);
  return object;
}

async function loadFBX(files, mgr) {
  const file = files.find(f => ext(f) === 'fbx');
  const url  = URL.createObjectURL(file);
  const obj  = await new Promise((ok, ng) => new FBXLoader(mgr).load(url, ok, undefined, ng));
  URL.revokeObjectURL(url);
  return obj;
}

async function loadDAE(files, mgr) {
  const file   = files.find(f => ext(f) === 'dae');
  const url    = URL.createObjectURL(file);
  const result = await new Promise((ok, ng) => new ColladaLoader(mgr).load(url, ok, undefined, ng));
  URL.revokeObjectURL(url);
  return result.scene;
}

async function loadGLTF(files, mgr) {
  const file = files.find(f => /\.(glb|gltf)$/i.test(f.name));
  const url  = URL.createObjectURL(file);
  const gltf = await new Promise((ok, ng) => new GLTFLoader(mgr).load(url, ok, undefined, ng));
  URL.revokeObjectURL(url);
  return gltf.scene;
}

// ── GLB エクスポート ──────────────────────────────────────

convertBtn.addEventListener('click', async () => {
  if (!selectedFiles.length) return;
  const mainFile = selectedFiles.find(f => MAIN_EXTS.has(ext(f)));
  const stem = mainFile ? mainFile.name.replace(/\.[^.]+$/, '') : 'model';

  convertBtn.disabled = true;

  // バックエンド（Blender）が使えるなら優先
  if (backendUrl) {
    setStatus('<span class="loading"><span class="spinner"></span>Blender で変換中...</span>');
    try {
      const form = new FormData();
      selectedFiles.forEach(f => form.append('files', f));
      const res = await fetch(`${backendUrl}/convert`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '不明なエラー' }));
        throw new Error(err.detail);
      }
      const blob = await res.blob();
      download(blob, stem + '.glb');
      setStatus(`<span class="success">✓ ${stem}.glb をダウンロードしました（Blender変換）</span>`);
      convertBtn.disabled = false;
      return;
    } catch (e) {
      setStatus(`<span class="loading"><span class="spinner"></span>バックエンドに失敗、ブラウザ変換にフォールバック中...</span>`);
    }
  }

  // フォールバック：Three.js クライアントサイド変換
  if (!loadedObject) {
    setStatus('<span class="error">モデルが読み込まれていません</span>');
    convertBtn.disabled = false;
    return;
  }
  try {
    const buf = await new Promise((ok, ng) =>
      new GLTFExporter().parse(loadedObject, ok, ng, { binary: true })
    );
    download(new Blob([buf], { type: 'model/gltf-binary' }), stem + '.glb');
    setStatus(`<span class="success">✓ ${stem}.glb をダウンロードしました（ブラウザ変換）</span>`);
  } catch (e) {
    setStatus(`<span class="error">変換エラー: ${e.message}</span>`);
  } finally {
    convertBtn.disabled = false;
  }
});

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
