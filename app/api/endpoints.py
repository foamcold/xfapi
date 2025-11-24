from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from app.core.config import config
from app.services.xf_service import xf_service
import os
import json

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
    special_symbol_mapping: Optional[dict] = None
    default_speaker: Optional[str] = None
    default_speed: Optional[int] = None
    default_volume: Optional[int] = None
    default_audio_type: Optional[str] = None
    generation_interval: Optional[float] = None
    cache_limit: Optional[int] = None
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
    settings = config.get_settings()
    
    voice = req.voice or settings.get("default_speaker", "聆小糖")
    speed = req.speed if req.speed is not None else settings.get("default_speed", 100)
    volume = req.volume if req.volume is not None else settings.get("default_volume", 100)
    audio_type = req.audio_type or settings.get("default_audio_type", "audio/mp3")
    
    # Resolve speaker name to code if needed
    # The API requires the 'param' (code), but user might pass 'name' or default might be a name.
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
                print(f"Error parsing extendUI for speaker {voice}: {e}")
                # Fallback to param (which is @style, likely to fail but better than crashing here)
                voice = param
        else:
            voice = param
    
    try:
        # Use the queue processing method
        resp = await xf_service.process_tts_request(req.text, voice, speed, volume, audio_type=audio_type)
        
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
    # Settings might contain sensitive info like password, so we should protect it or mask it.
    # But the frontend needs to see it to edit it.
    # If auth is enabled, we require key.
    verify_key(key)
    return config.get_settings()

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
    if req.generation_interval is not None:
        config.update_setting("generation_interval", req.generation_interval)
    if req.cache_limit is not None:
        config.update_setting("cache_limit", req.cache_limit)
        
    return {"status": "success", "settings": config.get_settings()}

@router.post("/login")
async def login(req: dict):
    # Simple check
    key = req.get("key")
    verify_key(key)
    return {"status": "success"}

@router.post("/reload_config")
async def reload_config(req: dict):
    key = req.get("key")
    verify_key(key)
    config.reload_config()
    return {"status": "success", "message": "Configuration reloaded"}
