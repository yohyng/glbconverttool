import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/api/config")
async def config():
    return JSONResponse({
        "backendUrl": os.environ.get("BACKEND_URL", ""),
    })
