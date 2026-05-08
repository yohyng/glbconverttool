import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

BLENDER = Path("/opt/blender/blender")
SCRIPT  = Path(__file__).parent / "blender_convert.py"

MAIN_EXTS = {".obj", ".fbx", ".dae", ".gltf", ".glb"}
ALL_EXTS  = MAIN_EXTS | {".mtl", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tga"}
MAX_SIZE  = 100 * 1024 * 1024  # 100 MB


@app.get("/health")
def health():
    return {"ok": True, "blender": BLENDER.exists()}


@app.post("/convert")
async def convert(files: list[UploadFile] = File(...)):
    for f in files:
        if Path(f.filename).suffix.lower() not in ALL_EXTS:
            raise HTTPException(400, f"非対応の形式: {f.filename}")

    main_file = next(
        (f for f in files if Path(f.filename).suffix.lower() in MAIN_EXTS), None
    )
    if not main_file:
        raise HTTPException(400, "変換対象ファイルが見つかりません（OBJ / FBX / DAE / GLTF / GLB）")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for f in files:
            data = await f.read()
            if len(data) > MAX_SIZE:
                raise HTTPException(413, f"{f.filename} が 100MB を超えています")
            (tmp / Path(f.filename).name).write_bytes(data)

        input_path  = tmp / Path(main_file.filename).name
        output_path = tmp / (input_path.stem + ".glb")

        try:
            result = subprocess.run(
                [str(BLENDER), "--background", "--python", str(SCRIPT),
                 "--", str(input_path), str(output_path)],
                capture_output=True, text=True, timeout=180
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "変換がタイムアウトしました（180秒）")

        if not output_path.exists():
            tail = (result.stdout + result.stderr)[-600:]
            raise HTTPException(500, f"変換に失敗しました:\n{tail}")

        glb = output_path.read_bytes()

    name = input_path.stem + ".glb"
    return Response(
        content=glb,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
