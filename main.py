from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.endpoints import router
import uvicorn

app = FastAPI(title="XFAPI - iFLYTEK TTS Proxy")

app.include_router(router, prefix="/api")

app.mount("/static", StaticFiles(directory="static"), name="static")
# Mount multitts for avatars
app.mount("/multitts", StaticFiles(directory="multitts"), name="multitts")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/settings_page")
async def read_settings():
    return FileResponse("static/settings.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
