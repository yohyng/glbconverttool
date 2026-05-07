const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const convertBtn = document.getElementById('convertBtn');
const fileList = document.getElementById('fileList');
const status = document.getElementById('status');

let selectedFiles = [];

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('drag-over');
});

dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('drag-over');
  handleFiles(e.dataTransfer.files);
});

dropzone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => handleFiles(fileInput.files));

function handleFiles(files) {
  selectedFiles = Array.from(files).filter(f =>
    /\.(obj|mtl)$/i.test(f.name)
  );
  renderFileList();
  status.innerHTML = '';
  convertBtn.disabled = !selectedFiles.some(f => /\.obj$/i.test(f.name));
}

function renderFileList() {
  fileList.innerHTML = selectedFiles.map(f => {
    const ext = f.name.split('.').pop().toLowerCase();
    return `<div class="file-item"><span class="ext">${ext}</span>${f.name}</div>`;
  }).join('');
}

convertBtn.addEventListener('click', async () => {
  if (!selectedFiles.length) return;

  status.innerHTML = '<span class="loading"><span class="spinner"></span>変換中...</span>';
  convertBtn.disabled = true;

  const formData = new FormData();
  selectedFiles.forEach(f => formData.append('files', f));

  try {
    const res = await fetch('/api/convert', { method: 'POST', body: formData });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: '不明なエラー' }));
      throw new Error(err.detail || '変換に失敗しました');
    }

    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const filename = disposition.match(/filename="(.+?)"/)?.[1] || 'model.glb';

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    status.innerHTML = `<span class="success">✓ ${filename} をダウンロードしました</span>`;
  } catch (e) {
    status.innerHTML = `<span class="error">エラー: ${e.message}</span>`;
  } finally {
    convertBtn.disabled = false;
  }
});
