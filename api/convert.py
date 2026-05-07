import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

app = FastAPI()

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED = {".obj", ".mtl"}


@app.post("/api/convert")
async def convert(files: list[UploadFile] = File(...)):
    for f in files:
        if Path(f.filename).suffix.lower() not in ALLOWED:
            raise HTTPException(400, f"非対応の形式: {f.filename}（OBJ / MTL のみ対応）")

    main_file = next(
        (f for f in files if Path(f.filename).suffix.lower() == ".obj"), None
    )
    if main_file is None:
        raise HTTPException(400, "OBJ ファイルが見つかりません")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        for f in files:
            content = await f.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(413, f"{f.filename} が 100MB を超えています")
            (tmpdir / Path(f.filename).name).write_bytes(content)

        input_path = tmpdir / Path(main_file.filename).name

        try:
            import trimesh

            scene = trimesh.load(str(input_path), force="scene")
            glb_bytes = scene.export(file_type="glb")
        except Exception as e:
            raise HTTPException(500, f"変換に失敗しました: {e}")

    output_name = input_path.stem + ".glb"
    return Response(
        content=glb_bytes,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
    )
