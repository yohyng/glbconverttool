# GLB Converter Tool

OBJ / FBX ファイルを GLB 形式に変換する Web アプリケーション。

## 概要

ブラウザから 3D モデルファイル（OBJ・FBX）をアップロードし、GLB（GL Transmission Format Binary）に変換してダウンロードできるツール。

## 対応フォーマット

| 入力 | 出力 |
|------|------|
| .obj (+ .mtl) | .glb |
| .fbx | .glb |

## ドキュメント

- [要件定義](docs/requirements.md)

## プロジェクト構成

```
glbconverttool/
├── frontend/       # Web UI
├── backend/        # 変換処理 API
└── docs/           # ドキュメント
```
