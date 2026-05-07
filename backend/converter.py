import subprocess
import tempfile
from pathlib import Path

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def convert_to_glb(input_path: Path) -> bytes:
    suffix = input_path.suffix.lower()
    if suffix == ".obj":
        return _convert_with_trimesh(input_path)
    elif suffix == ".fbx":
        return _convert_with_assimp(input_path)
    else:
        raise ValueError(f"Unsupported format: {suffix}")


def _convert_with_trimesh(input_path: Path) -> bytes:
    import trimesh

    scene = trimesh.load(str(input_path), force="scene")
    glb_bytes = scene.export(file_type="glb")
    if not glb_bytes:
        raise RuntimeError("trimesh produced empty output")
    return glb_bytes


def _convert_with_assimp(input_path: Path) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "output.glb"
        result = subprocess.run(
            ["assimp", "export", str(input_path), str(out_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0 or not out_path.exists():
            raise RuntimeError(result.stderr or result.stdout or "assimp failed")
        return out_path.read_bytes()
