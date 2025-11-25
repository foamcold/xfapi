from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from app.core.config import config
from app.services.xf_service import xf_service
from app.core.logger import log_queue, logger
import os
import json
import asyncio

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    speed: Optional[int] = None
    volume: Optional[int] = None
    audio_type: Optional[str] = None
    stream: Optional[bool] = False
    key: Optional[str] = None

class SettingsUpdate(BaseModel):
    auth_enabled: Optional[bool] = None
    admin_password: Optional[str] = None
    special_symbol_mapping: Optional[bool] = None
    default_speaker: Optional[str] = None
    default_speed: Optional[int] = None
    default_volume: Optional[int] = None
    default_audio_type: Optional[str] = None
    cache_limit: Optional[int] = None
    log_level: Optional[str] = None
    key: Optional[str] = None

def verify_key(key: Optional[str] = None):
    """验证API密钥"""
    settings = config.get_settings()
    
    # 如果认证未启用，直接返回
    if not settings.get("auth_enabled", False):
        return True
    
    # 如果认证已启用，检查密钥
    admin_password = settings.get("admin_password", "admin") or os.getenv("ADMIN_PASSWORD", "admin")
    
    if key == admin_password:
        return True
        
    raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/tts")
async def generate_tts(req: TTSRequest):
    verify_key(req.key)
    return await _process_tts(req)

@router.get("/tts")
async def generate_tts_get(
    text: str,
    voice: Optional[str] = None,
    speed: Optional[int] = None,
    volume: Optional[int] = None,
    audio_type: Optional[str] = None,
    stream: Optional[bool] = True,
    key: Optional[str] = None
):
    req = TTSRequest(
        text=text,
        voice=voice,
        speed=speed,
        volume=volume,
        audio_type=audio_type,
        stream=stream,
        key=key
    )
    verify_key(key)
    return await _process_tts(req)

async def _process_tts(req: TTSRequest):
    import time
    api_start = time.time()
    
    settings = config.get_settings()
    
    voice = req.voice or settings.get("default_speaker", "聪小糖")
    speed = req.speed if req.speed is not None else settings.get("default_speed", 100)
    volume = req.volume if req.volume is not None else settings.get("default_volume", 100)
    audio_type = req.audio_type or settings.get("default_audio_type", "audio/mp3")
    
    # 如果需要，将发音人名称解析为代码
    # API 需要 'param' (代码)，但用户可能会传递 'name'，或者默认值可能是一个名称。
    speakers = config.get_speakers()
    found_speaker = next((s for s in speakers if s.get("name") == voice), None)
    if found_speaker:
        param = found_speaker.get("param")
        if param == '@style':
            try:
                extend_ui = json.loads(found_speaker.get("extendUI", "[]"))
                if isinstance(extend_ui, list):
                    style_item = next((item for item in extend_ui if item.get("code") == "style"), None)
                    if style_item and style_item.get("value"):
                        voice = style_item["value"]
            except Exception as e:
                logger.error(f"解析发音人 {voice} 的 extendUI 时出错: {e}")
                # 回退到 param (即 @style，很可能会失败，但总比在这里崩溃要好)
                voice = param
        else:
            voice = param
    
    try:
        # 使用队列处理方法
        logger.debug(f"[API] 开始请求TTS服务")
        tts_call_start = time.time()
        
        resp = await xf_service.process_tts_request(req.text, voice, speed, volume, audio_type=audio_type)
        
        tts_call_time = (time.time() - tts_call_start) * 1000
        logger.debug(f"[API] TTS服务返回: {tts_call_time:.0f}ms")
        
        api_total = (time.time() - api_start) * 1000
        logger.debug(f"[API] 请求处理总耗时: {api_total:.0f}ms")
        
        if req.stream:
            return StreamingResponse(resp.iter_content(chunk_size=4096), media_type=audio_type)
        else:
            return StreamingResponse(resp.iter_content(chunk_size=4096), media_type=audio_type)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/speakers")
async def get_speakers():
    return config.get_speakers()

@router.get("/settings")
async def get_settings(key: Optional[str] = None):
    # 设置可能包含密码等敏感信息，因此我们应该保护或屏蔽它。
    # 但是前端需要看到它才能进行编辑。
    # 如果启用了身份验证，则需要密钥。
    verify_key(key)
    settings = config.get_settings().copy()
    settings["has_avatars"] = os.path.exists("data/multitts/xfpeiyin/avatar")
    return settings

@router.post("/settings")
async def update_settings(req: SettingsUpdate):
    verify_key(req.key)
    
    current_settings = config.get_settings()
    
    if req.auth_enabled is not None:
        config.update_setting("auth_enabled", req.auth_enabled)
    if req.admin_password is not None:
        config.update_setting("admin_password", req.admin_password)
    if req.special_symbol_mapping is not None:
        config.update_setting("special_symbol_mapping", req.special_symbol_mapping)
    if req.default_speaker is not None:
        config.update_setting("default_speaker", req.default_speaker)
    if req.default_speed is not None:
        config.update_setting("default_speed", req.default_speed)
    if req.default_volume is not None:
        config.update_setting("default_volume", req.default_volume)
    if req.default_audio_type is not None:
        config.update_setting("default_audio_type", req.default_audio_type)
    if req.cache_limit is not None:
        config.update_setting("cache_limit", req.cache_limit)
    if req.log_level is not None:
        config.update_setting("log_level", req.log_level)
        
    return {"status": "success", "settings": config.get_settings()}

@router.post("/login")
async def login(req: dict):
    # 简单检查
    key = req.get("key")
    verify_key(key)
    return {"status": "success"}

@router.post("/reload_config")
async def reload_config(req: dict):
    key = req.get("key")
    verify_key(key)
    try:
        config.reload_config()
        logger.info("配置已通过 API 请求重新加载。")
        return {"status": "success", "message": "Configuration reloaded"}
    except Exception as e:
        logger.error(f"通过 API 重新加载配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
async def stream_logs(request: Request):
    async def log_generator():
        queue = asyncio.Queue()
        # 将队列放入日志处理程序，以便新日志进入此特定队列
        log_queue.subscribe(queue)
        
        try:
            # 首先，发送所有历史日志
            initial_logs = list(log_queue)
            for log_record in initial_logs:
                yield f"data: {json.dumps(log_record)}\n\n"

            # 然后，监听新日志
            while True:
                try:
                    # 等待新日志，设置超时以定期检查连接状态
                    log_record = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(log_record)}\n\n"
                    queue.task_done()
                except asyncio.TimeoutError:
                    # 超时后，检查客户端是否已断开连接
                    if await request.is_disconnected():
                        break
        except asyncio.CancelledError:
            # 当服务器关闭时，Uvicorn 会取消任务，捕获此异常
            logger.debug("日志流任务被取消。")
        finally:
            # 确保我们取消订阅队列以避免内存泄漏
            log_queue.unsubscribe(queue)
            logger.debug("日志流客户端已断开连接并已取消订阅。")

    return StreamingResponse(log_generator(), media_type="text/event-stream")
