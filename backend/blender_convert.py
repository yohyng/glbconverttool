"""Blender Python script — called headlessly by the FastAPI server.

Usage (inside Blender):
  blender --background --python blender_convert.py -- <input> <output.glb>
"""

import sys
from pathlib import Path

import bpy

# ── 引数取得 ──────────────────────────────────────────────

argv = sys.argv
try:
    sep = argv.index("--")
except ValueError:
    print("ERROR: no arguments after --"); sys.exit(1)

args = argv[sep + 1:]
if len(args) < 2:
    print("ERROR: usage: -- <input> <output.glb>"); sys.exit(1)

input_path  = Path(args[0])
output_path = Path(args[1])
ext         = input_path.suffix.lower()

# ── シーン初期化 ──────────────────────────────────────────

bpy.ops.wm.read_factory_settings(use_empty=True)
for obj in bpy.data.objects:
    bpy.data.objects.remove(obj, do_unlink=True)

# ── インポート ────────────────────────────────────────────

try:
    if ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(input_path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(input_path))
    elif ext == ".dae":
        bpy.ops.wm.collada_import(filepath=str(input_path))
    elif ext in (".gltf", ".glb"):
        bpy.ops.import_scene.gltf(filepath=str(input_path))
    else:
        print(f"ERROR: unsupported format: {ext}"); sys.exit(1)
except Exception as e:
    print(f"ERROR: import failed: {e}"); sys.exit(1)

if not bpy.context.scene.objects:
    print("ERROR: no objects after import"); sys.exit(1)

# ── GLB エクスポート ──────────────────────────────────────

try:
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_colors=True,
        export_cameras=False,
        export_lights=False,
        export_apply=False,
    )
    print(f"SUCCESS: {output_path}")
except Exception as e:
    print(f"ERROR: export failed: {e}"); sys.exit(1)
