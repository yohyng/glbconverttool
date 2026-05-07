import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/api/version")
async def version():
    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")
    short = sha[:7] if sha else "dev"
    return JSONResponse({"version": short})
