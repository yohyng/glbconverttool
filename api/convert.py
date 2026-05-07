import tempfile
from pathlib import Path

import trimesh
import trimesh.visual.material as trimesh_mat
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

app = FastAPI()

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED = {".obj", ".mtl"}


def _extract_color(mat) -> list:
    """どのマテリアル型からでも 0-1 RGBA を返す。"""
    import numpy as np

    for attr in ("diffuse", "baseColorFactor", "main_color"):
        val = getattr(mat, attr, None)
        if val is None:
            continue
        try:
            c = np.array(val, dtype=float).flatten()[:4]
            if c.max() > 1.0:        # 0-255 スケールなら正規化
                c = c / 255.0
            c = np.clip(c, 0.0, 1.0)
            if len(c) < 4:
                c = np.append(c, np.ones(4 - len(c)))
            return c.tolist()
        except Exception:
            pass
    return [0.8, 0.8, 0.8, 1.0]


def _fix_materials(scene: trimesh.Scene) -> None:
    """全ジオメトリのマテリアルを metallic=0 の PBR に強制変換する。

    trimesh が生成する SimpleMaterial / PBRMaterial は metallicFactor が
    1.0 になることがあり、環境マップなしのビューアで真っ黒に見える。
    色を保持しつつ非メタリック PBR として上書きする。
    """
    for geom in scene.geometry.values():
        visual = getattr(geom, "visual", None)
        if visual is None:
            continue
        mat = getattr(visual, "material", None)
        if mat is None:
            continue
        try:
            color = _extract_color(mat)
            visual.material = trimesh_mat.PBRMaterial(
                baseColorFactor=color,
                metallicFactor=0.0,
                roughnessFactor=0.9,
            )
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
