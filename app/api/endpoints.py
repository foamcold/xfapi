from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from app.core.config import config
from app.services.xf_service import xf_service
import os

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
    key: Optional[str] = None

def verify_key(key: Optional[str] = None):
    settings = config.get_settings()
    auth_enabled = settings.get("auth_enabled", False) or os.getenv("AUTH_ENABLED", "false").lower() == "true"
    
    if not auth_enabled:
        return True
        
    admin_password = settings.get("admin_password", "admin") or os.getenv("ADMIN_PASSWORD", "admin")
    
    if key == admin_password:
        return True
        
    raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/tts")
async def generate_tts(req: TTSRequest):
    verify_key(req.key)
    
    settings = config.get_settings()
    
    voice = req.voice or settings.get("default_speaker", "聆小糖")
    speed = req.speed if req.speed is not None else settings.get("default_speed", 100)
    volume = req.volume if req.volume is not None else settings.get("default_volume", 100)
    audio_type = req.audio_type or settings.get("default_audio_type", "audio/mp3")
    
    try:
        url = xf_service.get_audio_url(req.text, voice, speed, volume, audio_type=audio_type)
        
        if req.stream:
            # Return stream
            resp = xf_service.get_audio_stream(url)
            return StreamingResponse(resp.iter_content(chunk_size=4096), media_type=audio_type)
        else:
            # Return URL or redirect? Requirement says "api proxy", usually implies returning the audio content.
            # But "stream=False" might imply returning the full file at once or just the URL?
            # Let's assume stream=False means we fetch it all and return it, or just return the URL if requested?
            # Standard TTS APIs usually return audio.
            # Let's return the audio content fully buffered if not streaming, or just stream it anyway but with different headers?
            # Actually, for a proxy, streaming is usually best.
            # If the user wants the URL, maybe we can have a separate endpoint or param.
            # But for now, let's just stream it.
            resp = xf_service.get_audio_stream(url)
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
        
    return {"status": "success", "settings": config.get_settings()}

@router.post("/login")
async def login(req: dict):
    # Simple check
    key = req.get("key")
    verify_key(key)
    return {"status": "success"}
