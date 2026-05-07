import tempfile
from pathlib import Path

import trimesh
import trimesh.visual.material as trimesh_mat
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

app = FastAPI()

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED = {".obj", ".mtl"}


def _fix_materials(scene: trimesh.Scene) -> None:
    """OBJ/MTL の SimpleMaterial を PBRMaterial に変換して色を保持する。

    trimesh は MTL の Kd（拡散色）を GLB エクスポート時に正しく
    baseColorFactor へ変換しないため、to_pbr() で明示的に変換する。
    """
    for geom in scene.geometry.values():
        visual = getattr(geom, "visual", None)
        if visual is None:
            continue
        mat = getattr(visual, "material", None)
        if mat is None:
            continue
        if isinstance(mat, trimesh_mat.PBRMaterial):
            continue
        try:
            visual.material = mat.to_pbr()
        except Exception:
            pass


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
            scene = trimesh.load(str(input_path), force="scene")
            _fix_materials(scene)
            glb_bytes = scene.export(file_type="glb")
        except Exception as e:
            raise HTTPException(500, f"変換に失敗しました: {e}")

    output_name = input_path.stem + ".glb"
    return Response(
        content=glb_bytes,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
    )
