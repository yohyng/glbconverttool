import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from converter import MAX_FILE_SIZE, convert_to_glb

app = FastAPI(title="GLB Converter")

ALLOWED_EXTENSIONS = {".obj", ".fbx", ".mtl"}
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (FRONTEND_DIR / "index.html").read_text()


@app.post("/convert")
async def convert(files: list[UploadFile] = File(...)):
    for f in files:
        if Path(f.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file: {f.filename}")

    main_file = next(
        (f for f in files if Path(f.filename).suffix.lower() in {".obj", ".fbx"}),
        None,
    )
    if main_file is None:
        raise HTTPException(400, "OBJ または FBX ファイルが含まれていません")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        for f in files:
            dest = tmpdir / Path(f.filename).name
            content = await f.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(413, f"{f.filename} が 100MB を超えています")
            dest.write_bytes(content)

        input_path = tmpdir / Path(main_file.filename).name

        try:
            glb_bytes = convert_to_glb(input_path)
        except Exception as e:
            raise HTTPException(500, f"変換に失敗しました: {e}")

    output_name = input_path.stem + ".glb"
    return Response(
        content=glb_bytes,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
    )
