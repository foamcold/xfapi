from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.endpoints import router
import uvicorn

from app.core.config import config
from app.core.logger import setup_logger, logger
from contextlib import asynccontextmanager
import asyncio
import time
from urllib.parse import unquote

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 首先，配置日志系统
    setup_logger()
    
    # 2. 然后，加载应用配置
    config.load_config()
    settings = config.get_settings()
    port = settings.get("port", 8501)
    
    async def print_banner():
        await asyncio.sleep(0.5)
        logger.info("="*50)
        logger.info("XFAPI 服务已启动")
        logger.info(f"Web 界面: http://localhost:{port}")
        logger.info(f"API 文档: http://localhost:{port}/docs")
        logger.info("="*50)
        
    asyncio.create_task(print_banner())
    yield

app = FastAPI(title="XFAPI - iFLYTEK TTS Proxy", lifespan=lifespan)

# 添加日志中间件 (纯 ASGI 中间件，避免 BaseHTTPMiddleware 阻塞 SSE 流)
class LoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        status_code = [200] # 使用列表以便在闭包中修改

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        
        process_time = (time.time() - start_time) * 1000
        
        # 提取信息
        path = unquote(scope["path"])
        method = scope["method"]
        client = scope.get("client")
        host = client[0] if client else "unknown"
        port = client[1] if client else 0
        http_version = scope.get("http_version", "1.1")
        
        # 排除 /api/logs 的日志，避免刷屏
        if path != "/api/logs":
            log_message = f'{host}:{port} - "{method} {path} HTTP/{http_version}" {status_code[0]} ({process_time:.2f}ms)'
            logger.info(log_message)

app.add_middleware(LoggingMiddleware)

app.include_router(router, prefix="/api")

import os

app.mount("/static", StaticFiles(directory="static"), name="static")
# 为头像挂载 multitts
if not os.path.exists("data/multitts"):
    os.makedirs("data/multitts")
app.mount("/multitts", StaticFiles(directory="data/multitts"), name="multitts")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/settings_page")
async def read_settings():
    return FileResponse("static/settings.html")

@app.get("/logs_page")
async def read_logs():
    return FileResponse("static/logs.html")



if __name__ == "__main__":
    # 从配置中获取端口，如果 lifespan 还没运行，这里会加载一次
    # 但在 lifespan 中会重新加载
    settings = config.get_settings()
    port = settings.get("port", 8501)
    
    import uvicorn
    # 不再需要自定义 log_config，因为我们用中间件处理了所有请求日志
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, log_config=None)
