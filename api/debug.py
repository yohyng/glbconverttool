import traceback
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI()


@app.post("/api/debug")
async def debug(files: list[UploadFile] = File(...)):
    try:
        import trimesh

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            for f in files:
                (tmpdir / Path(f.filename).name).write_bytes(await f.read())

            obj_file = next(
                (tmpdir / Path(f.filename).name for f in files
                 if Path(f.filename).suffix.lower() == ".obj"),
                None,
            )
            if obj_file is None:
                return JSONResponse({"error": "no OBJ"})

            scene = trimesh.load(str(obj_file), force="scene")

            result = {"geometries": {}}
            for name, geom in scene.geometry.items():
                visual = getattr(geom, "visual", None)
                mat = getattr(visual, "material", None)

                diffuse = getattr(mat, "diffuse", None) if mat else None
                if hasattr(diffuse, "tolist"):
                    diffuse = diffuse.tolist()

                base_color = getattr(mat, "baseColorFactor", None) if mat else None
                if hasattr(base_color, "tolist"):
                    base_color = base_color.tolist()

                result["geometries"][name] = {
                    "visual_type": type(visual).__name__,
                    "material_type": type(mat).__name__ if mat else None,
                    "diffuse": diffuse,
                    "baseColorFactor": base_color,
                    "metallicFactor": getattr(mat, "metallicFactor", None) if mat else None,
                }

            return JSONResponse(result)

    except Exception:
        return JSONResponse({"error": traceback.format_exc()}, status_code=500)
