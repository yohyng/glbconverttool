from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

_VERSION = (Path(__file__).parent.parent / "VERSION").read_text().strip()


@app.get("/api/version")
async def version():
    return JSONResponse({"version": _VERSION})
