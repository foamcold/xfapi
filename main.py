from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.endpoints import router
import uvicorn

from app.core.config import config

from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = config.get_settings()
    port = settings.get("port", 8501)
    
    async def print_banner():
        await asyncio.sleep(1)
        print("\n" + "="*50)
        print("XFAPI 服务已启动")
        print(f"Web 界面: http://localhost:{port}")
        print(f"API 文档: http://localhost:{port}/docs")
        print("="*50 + "\n")
        
    asyncio.create_task(print_banner())
    yield

app = FastAPI(title="XFAPI - iFLYTEK TTS Proxy", lifespan=lifespan)

app.include_router(router, prefix="/api")

import os

app.mount("/static", StaticFiles(directory="static"), name="static")
# Mount multitts for avatars
if not os.path.exists("multitts"):
    os.makedirs("multitts")
app.mount("/multitts", StaticFiles(directory="multitts"), name="multitts")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/settings_page")
async def read_settings():
    return FileResponse("static/settings.html")



if __name__ == "__main__":
    import colorama
    colorama.init()
    import copy
    settings = config.get_settings()
    port = settings.get("port", 8501)
    
    # Configure logging to decode URLs
    log_config = copy.deepcopy(uvicorn.config.LOGGING_CONFIG)
    log_config["formatters"]["access"]["()"] = "app.core.logging.DecodedAccessFormatter"
    
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, log_config=log_config)
