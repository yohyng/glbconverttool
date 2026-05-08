import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { MTLLoader } from 'three/addons/loaders/MTLLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// ── シーン構築 ─────────────────────────────────────────────

function makeScene(canvasId) {
  const canvas = document.getElementById(canvasId);
  const wrap = canvas.parentElement;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf0f0f0);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  camera.position.set(2, 1.5, 4);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;

  scene.add(new THREE.AmbientLight(0xffffff, 1.2));
  const sun = new THREE.DirectionalLight(0xffffff, 2.0);
  sun.position.set(5, 10, 7);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xffffff, 0.6);
  fill.position.set(-5, 2, -7);
  scene.add(fill);

  function resize() {
    const w = wrap.clientWidth;
    const h = wrap.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  resize();
  new ResizeObserver(resize).observe(wrap);

  return { renderer, scene, camera, controls, current: null };
}

const left  = makeScene('canvas-left');
const right = makeScene('canvas-right');

// ── カメラ同期 ────────────────────────────────────────────

const syncCam = document.getElementById('syncCam');
let syncing = false;

function syncFrom(src, dst) {
  src.controls.addEventListener('change', () => {
    if (!syncCam.checked || syncing) return;
    syncing = true;
    dst.camera.position.copy(src.camera.position);
    dst.camera.quaternion.copy(src.camera.quaternion);
    dst.controls.target.copy(src.controls.target);
    dst.controls.update();
    syncing = false;
  });
}
syncFrom(left, right);
syncFrom(right, left);

// ── アニメーションループ ───────────────────────────────────

(function animate() {
  requestAnimationFrame(animate);
  left.controls.update();
  right.controls.update();
  left.renderer.render(left.scene, left.camera);
  right.renderer.render(right.scene, right.camera);
})();

// ── カメラをモデルに合わせる ──────────────────────────────

function fitCamera(state, object) {
  const box = new THREE.Box3().setFromObject(object);
  const size = box.getSize(new THREE.Vector3()).length();
  const center = box.getCenter(new THREE.Vector3());

  state.camera.near = size / 100;
  state.camera.far  = size * 100;
  state.camera.updateProjectionMatrix();
  state.camera.position.copy(center).add(new THREE.Vector3(size * 0.8, size * 0.6, size * 1.4));
  state.controls.target.copy(center);
  state.controls.update();
}

function setModel(state, object) {
  if (state.current) state.scene.remove(state.current);
  state.scene.add(object);
  state.current = object;
  fitCamera(state, object);
}

// ── OBJ マテリアル修正（Kd=黒 → Ks を使うメタリックワークフロー対応）──

function fixOBJMaterials(object) {
  object.traverse(node => {
    if (!node.isMesh) return;
    const mats = Array.isArray(node.material) ? node.material : [node.material];
    node.material = mats.map(mat => {
      if (!mat) return mat;
      const kd = mat.color ?? new THREE.Color(0.8, 0.8, 0.8);
      const ks = mat.specular ?? new THREE.Color(0, 0, 0);
      const ns = mat.shininess ?? 0;
      const opacity = mat.opacity ?? 1.0;
      const transparent = opacity < 1.0;

      const roughness = Math.max(0.04, Math.sqrt(2.0 / (ns + 2.0)));

      let color, metalness;
      if (kd.r + kd.g + kd.b < 0.03 && ks.r + ks.g + ks.b > 0.03) {
        // メタリックワークフロー: Ks を色として使う
        color = ks.clone();
        metalness = ns > 100 ? 1.0 : 0.0;
      } else {
        color = kd.clone();
        metalness = 0.0;
      }

      return new THREE.MeshStandardMaterial({
        color,
        metalness,
        roughness: metalness === 0 ? Math.max(roughness, 0.4) : roughness,
        transparent,
        opacity: Math.max(opacity, transparent ? 0.15 : 1.0),
        side: THREE.DoubleSide,
      });
    });
    if (!Array.isArray(node.material)) node.material = node.material[0];
  });
  return object;
}

// ── OBJ ロード ────────────────────────────────────────────

async function loadOBJ(objFile, mtlFile) {
  const objUrl = URL.createObjectURL(objFile);
  let object;

  if (mtlFile) {
    const mtlUrl = URL.createObjectURL(mtlFile);
    const materials = await new Promise((res, rej) =>
      new MTLLoader().load(mtlUrl, res, undefined, rej));
    materials.preload();
    URL.revokeObjectURL(mtlUrl);
    const loader = new OBJLoader();
    loader.setMaterials(materials);
    object = await new Promise((res, rej) => loader.load(objUrl, res, undefined, rej));
  } else {
    object = await new Promise((res, rej) =>
      new OBJLoader().load(objUrl, res, undefined, rej));
  }

  URL.revokeObjectURL(objUrl);
  return fixOBJMaterials(object);
}

// ── GLB ロード ────────────────────────────────────────────

async function loadGLB(file) {
  const url = URL.createObjectURL(file);
  const gltf = await new Promise((res, rej) =>
    new GLTFLoader().load(url, res, undefined, rej));
  URL.revokeObjectURL(url);
  return gltf.scene;
}

// ── ドロップゾーン共通処理 ────────────────────────────────

function setupDrop(side, state, accept, loader) {
  const drop   = document.getElementById(`drop-${side}`);
  const input  = document.getElementById(`input-${side}`);
  const label  = document.getElementById(`label-${side}`);
  const reload = document.getElementById(`reload-${side}`);

  async function handle(files) {
    label.textContent = '読み込み中...';
    try {
      const obj = await loader(files);
      setModel(state, obj);
      // OBJ や GLB を優先表示（MTL より先に）
      const priority = ['.obj', '.glb'];
      const main = Array.from(files).find(f => priority.some(e => f.name.endsWith(e)))
                ?? Array.from(files).find(f => accept.some(e => f.name.endsWith(e)));
      label.textContent = main?.name ?? '';
      drop.classList.add('hidden');
      reload.hidden = false;
    } catch (e) {
      label.textContent = 'エラー: ' + e.message;
    }
  }

  drop.addEventListener('click', () => input.click());
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('drag-over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('drag-over'));
  drop.addEventListener('drop', e => {
    e.preventDefault();
    drop.classList.remove('drag-over');
    handle(e.dataTransfer.files);
  });
  input.addEventListener('change', () => handle(input.files));
  reload.addEventListener('click', () => {
    drop.classList.remove('hidden');
    reload.hidden = true;
    label.textContent = 'ファイルを選択';
    input.value = '';
  });
}

setupDrop('left',  left,  ['.obj', '.mtl'],
  files => loadOBJ(
    Array.from(files).find(f => f.name.endsWith('.obj')),
    Array.from(files).find(f => f.name.endsWith('.mtl')),
  ));

setupDrop('right', right, ['.glb'],
  files => loadGLB(Array.from(files).find(f => f.name.endsWith('.glb'))));
