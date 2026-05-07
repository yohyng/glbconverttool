import math
import tempfile
from pathlib import Path

import trimesh
import trimesh.visual.material as trimesh_mat
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

app = FastAPI()

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED = {".obj", ".mtl"}


def _parse_scalar(val, default: float) -> float:
    """float または ['0.0000'] 形式の値を float に変換する。"""
    if val is None:
        return default
    if isinstance(val, list):
        val = val[0]
    return float(val)


def _fix_materials(scene: trimesh.Scene) -> None:
    """OBJ/MTL の SimpleMaterial を正しい PBR マテリアルに変換する。

    OBJ のメタリックワークフロー:
      - 通常素材: Kd に色 → baseColorFactor に使用
      - 金属素材: Kd=黒、Ks に色 → Ks を baseColorFactor に使用、metallic=1
      - ガラス等: d < 1 → alphaMode=BLEND
    Phong の Ns → PBR roughness は sqrt(2/(Ns+2)) で変換。
    """
    for geom in scene.geometry.values():
        visual = getattr(geom, "visual", None)
        mat = getattr(visual, "material", None)
        if mat is None:
            continue

        kwargs = getattr(mat, "kwargs", {}) or {}

        kd = [float(v) for v in kwargs.get("kd", [0.8, 0.8, 0.8])]
        ks = [float(v) for v in kwargs.get("ks", [0.0, 0.0, 0.0])]
        ns = _parse_scalar(kwargs.get("ns"), 0.0)
        # d=0 は完全透明だが最低 0.05 を確保して不可視にならないようにする
        d = max(_parse_scalar(kwargs.get("d"), 1.0), 0.05)

        # Phong Ns → PBR roughness (標準変換式)
        roughness = math.sqrt(2.0 / (ns + 2.0)) if ns >= 0 else 1.0
        roughness = float(max(0.04, min(1.0, roughness)))

        # Kd が黒で Ks に色がある → メタリックワークフロー
        if sum(kd) < 0.01 and sum(ks) > 0.01:
            base_color = ks[:3] + [d]
            metallic = 1.0 if ns > 100 else 0.0
            # 非メタリック（Ns低）は最低限の roughness を確保して白っぽく見せる
            if metallic == 0.0:
                roughness = max(roughness, 0.5)
        else:
            base_color = kd[:3] + [d]
            metallic = 0.0
            # 環境マップなしビューアでも白く見えるよう roughness に下限を設ける
            roughness = max(roughness, 0.4)

        # d=0 のガラスは少し見える程度に
        if d <= 0.05:
            d = 0.15
            base_color = base_color[:3] + [d]

        alpha_mode = "BLEND" if d < 1.0 else "OPAQUE"

        try:
            visual.material = trimesh_mat.PBRMaterial(
                baseColorFactor=base_color,
                metallicFactor=metallic,
                roughnessFactor=roughness,
                alphaMode=alpha_mode,
                doubleSided=True,  # キューブのストライプ防止
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
            scene = trimesh.load(str(input_path), force="scene", process=False)
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
