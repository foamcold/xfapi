import json
import base64
import hashlib
import requests
import asyncio
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from urllib.parse import quote
from app.core.config import config

import os
import shutil

class XFService:
    AES_KEY = b'G%.g7"Y&Nf^40Ee<'
    SIGN_URL = "https://peiyin.xunfei.cn/web-server/1.0/works_synth_sign"
    SYNTH_URL_BASE = "https://peiyin.xunfei.cn/synth"
    CACHE_DIR = "cache"
    
    SPECIAL_SYMBOLS_MAP = {
        '#': '井号', '@': '艾特', '&': '和', '*': '星号', '%': '百分号',
        '$': '美元符号', '^': '脱字符', '~': '波浪号', '`': '反引号',
        '\\': '反斜杠', '/': '斜杠', '|': '竖线', '[': '左方括号',
        ']': '右方括号', '{': '左花括号', '}': '右花括号', '<': '小于号',
        '>': '大于号', '(': '左括号', ')': '右括号', '+': '加号',
        '=': '等号', ':': '冒号', ';': '分号', '"': '双引号',
        "'": '单引号', '?': '问号', '!': '感叹号'
    }

    def __init__(self):
        import threading
        self._thread_local = threading.local()
        self.queue = None
        self.worker_task = None
        
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

    async def start_worker(self):
        if self.queue is None:
            self.queue = asyncio.Queue()
            self.worker_task = asyncio.create_task(self._worker())

    def _get_cache_key(self, text: str, voice_code: str, speed: int, volume: int, pitch: int, audio_type: str) -> str:
        # MD5(text + voice + speed + volume + pitch + type)
        raw = f"{text}_{voice_code}_{speed}_{volume}_{pitch}_{audio_type}"
        return hashlib.md5(raw.encode('utf-8')).hexdigest() + ("." + audio_type.split('/')[-1] if '/' in audio_type else ".mp3")

    def _clean_cache(self):
        limit = config.get_settings().get("cache_limit", 100)
        if limit <= 0:
            return

        files = [os.path.join(self.CACHE_DIR, f) for f in os.listdir(self.CACHE_DIR)]
        files = [f for f in files if os.path.isfile(f)]
        
        if len(files) > limit:
            # Sort by mtime (oldest first)
            files.sort(key=os.path.getmtime)
            # Delete oldest
            for f in files[:len(files) - limit]:
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"Error cleaning cache file {f}: {e}")

    async def _worker(self):
        while True:
            future, args = await self.queue.get()
            try:
                # args: (text, voice_code, speed, volume, pitch, audio_type)
                text, voice_code, speed, volume, pitch, audio_type = args
                
                url = self.get_audio_url(*args)
                resp = self.get_audio_stream(url)
                
                # Save to cache if enabled
                limit = config.get_settings().get("cache_limit", 100)
                if limit > 0:
                    cache_key = self._get_cache_key(*args)
                    cache_path = os.path.join(self.CACHE_DIR, cache_key)
                    
                    # We need to read the content to save it, but resp is a stream.
                    # We can stream to file and then re-open for the user?
                    # Or just save chunks as we iterate? 
                    # Endpoints expects an iterator.
                    # Let's save to a temp file first, then move to cache, then serve from cache?
                    # Or just read all into memory (might be large)?
                    # Better: Stream to file, then serve file stream.
                    
                    with open(cache_path, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=4096):
                            if chunk:
                                f.write(chunk)
                    
                    self._clean_cache()
                    
                    # Return a mock response that reads from the file
                    class FileStreamResponse:
                        def __init__(self, path):
                            self.path = path
                        def iter_content(self, chunk_size=4096):
                            with open(self.path, 'rb') as f:
                                while True:
                                    data = f.read(chunk_size)
                                    if not data:
                                        break
                                    yield data
                                    
                    if not future.done():
                        future.set_result(FileStreamResponse(cache_path))
                else:
                    if not future.done():
                        future.set_result(resp)
                
                # Wait for configured delay after successful generation
                delay = config.get_settings().get("generation_interval", 1.0)
                await asyncio.sleep(float(delay))
                
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            finally:
                self.queue.task_done()

    async def process_tts_request(self, text: str, voice_code: str, speed: int, volume: int, pitch: int = 50, audio_type: str = "mp3"):
        # Check cache first
        limit = config.get_settings().get("cache_limit", 100)
        if limit > 0:
            cache_key = self._get_cache_key(text, voice_code, speed, volume, pitch, audio_type)
            cache_path = os.path.join(self.CACHE_DIR, cache_key)
            
            if os.path.exists(cache_path):
                # Update mtime
                os.utime(cache_path, None)
                
                # Return mock response
                class FileStreamResponse:
                    def __init__(self, path):
                        self.path = path
                    def iter_content(self, chunk_size=4096):
                        with open(self.path, 'rb') as f:
                            while True:
                                data = f.read(chunk_size)
                                if not data:
                                    break
                                yield data
                
                # Return immediately, bypassing queue
                return FileStreamResponse(cache_path)

        if self.queue is None:
            await self.start_worker()
            
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        await self.queue.put((future, (text, voice_code, speed, volume, pitch, audio_type)))
        return await future

    def _get_session(self):
        if not hasattr(self._thread_local, "session"):
            session = requests.Session()
            retry = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self._thread_local.session = session
        return self._thread_local.session

    def _close_session(self):
        if hasattr(self._thread_local, "session"):
            try:
                self._thread_local.session.close()
            except:
                pass
            del self._thread_local.session

    def _process_special_symbols(self, text: str) -> str:
        if not config.get_settings().get("special_symbol_mapping", False):
            return text
        
        processed_text = ""
        for char in text:
            processed_text += self.SPECIAL_SYMBOLS_MAP.get(char, char)
        return processed_text

    def _encrypt(self, data: dict) -> str:
        cipher = AES.new(self.AES_KEY, AES.MODE_ECB)
        json_str = json.dumps(data)
        encrypted_bytes = cipher.encrypt(pad(json_str.encode('utf-8'), AES.block_size))
        return base64.b64encode(encrypted_bytes).decode('utf-8')

    def _decrypt(self, encrypted_str: str) -> dict:
        cipher = AES.new(self.AES_KEY, AES.MODE_ECB)
        encrypted_bytes = base64.b64decode(encrypted_str)
        decrypted_bytes = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
        return json.loads(decrypted_bytes.decode('utf-8'))

    def _process_text_tags(self, text: str, pitch: int, emo: str, emo_value: int = 0) -> str:
        # Pitch tag: [te50]
        pitch_tag = f"[te{pitch}]" if pitch != 50 else "" # Assuming 50 is default/neutral? Plugin says: pitch ? '[te' + pitch + ']' : '';
        # Actually plugin sends it if pitch is truthy. If pitch is 0? 
        # Let's follow plugin: pitch = pitch ? '[te' + pitch + ']' : '';
        # But we pass pitch as int. If pitch is 0, it sends nothing?
        # Let's assume our pitch 50 is standard.
        # Plugin logic: pitch = pitch ? ...
        # If we pass pitch, we should add it.
        pitch_tag = f"[te{pitch}]" if pitch is not None else ""
        
        # Emotion tag: [em{emo}:{emo_value}]
        emo_tag = f"[em{emo}:{emo_value}]" if emo else ""
        
        return f"{pitch_tag}{emo_tag}{text}"

    def get_audio_url(self, text: str, voice_code: str, speed: int, volume: int, pitch: int = 50, audio_type: str = "mp3") -> str:
        processed_text = self._process_special_symbols(text)
        
        # Handle custom voice format (vid_emo)
        vid = voice_code
        emo = ""
        if "_" in voice_code:
            parts = voice_code.split("_")
            vid = parts[0]
            if len(parts) > 1:
                emo = parts[1]

        # Parameter mapping logic
        # speed: 0-100 -> -200 to 200 (Slope 4)
        # 100-300 -> 200 to 500 (Slope 1.5)
        sp = int(speed)
        if sp <= 100:
            final_speed = sp * 4 - 200
        else:
            final_speed = int(200 + (sp - 100) * 1.5)
            
        final_volume = int(int(volume) * 0.4 - 20)
        
        # Add tags to text
        # We default emo_value to 0 as we don't have a slider for it yet
        tagged_text = self._process_text_tags(processed_text, pitch, emo, 0)
        
        # Calculate hash
        txt = tagged_text
        m = hashlib.md5()
        m.update(txt.encode('utf-8'))
        txt_hash = m.hexdigest()
        
        req_data = {
            "synth_text_hash_code": txt_hash
        }
        
        encrypted_req = self._encrypt(req_data)
        final_req = json.dumps({"req": encrypted_req})
        
        headers = {
            'content-type': 'application/json;charset=UTF-8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://peiyin.xunfei.cn/',
            'Origin': 'https://peiyin.xunfei.cn',
        }
        
        # Retry loop with backoff
        import time
        import random
        max_retries = 5
        
        for attempt in range(max_retries):
            session = self._get_session()
            try:
                resp = session.post(self.SIGN_URL, data=final_req, headers=headers, timeout=10)
                resp.raise_for_status()
                
                resp_json = resp.json()
                
                if "body" not in resp_json:
                     raise Exception(f"Unexpected response format: {resp_json}")

                decrypted_body = self._decrypt(resp_json["body"])
                
                txt_cnt = quote(txt)
                
                final_url = (
                    f"{self.SYNTH_URL_BASE}?"
                    f"ts={decrypted_body['time_stamp']}&"
                    f"sign={decrypted_body['sign_text']}&"
                    f"sid=&vid={vid}&"
                    f"volume={final_volume}&"
                    f"speed={final_speed}&"
                    f"content={txt_cnt}&"
                    f"listen=0"
                )
                
                return final_url

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                # Force close session to clear broken connection/SSL state
                self._close_session()
                
                if attempt == max_retries - 1:
                    raise
                
                # Linear backoff with higher base: 2s, 4s, 6s, 8s, 10s... + jitter
                sleep_time = ((attempt + 1) * 2) + random.uniform(0, 1)
                print(f"Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)

    def get_audio_stream(self, url: str):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://peiyin.xunfei.cn/',
            'Connection': 'close'
        }
        
        import time
        import random
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                # Create a fresh session for each attempt to ensure no stale connections
                session = requests.Session()
                # We can still use HTTPAdapter for standard retries within the session, 
                # but the outer loop handles the "nuclear option" of a fresh session.
                retry = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "OPTIONS"]
                )
                adapter = HTTPAdapter(max_retries=retry)
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                
                resp = session.get(url, headers=headers, stream=True, timeout=30)
                resp.raise_for_status()
                return resp
                
            except Exception as e:
                print(f"Stream attempt {attempt + 1} failed: {e}")
                
                if attempt == max_retries - 1:
                    raise
                
                # Linear backoff with higher base: 2s, 4s, 6s, 8s, 10s... + jitter
                sleep_time = ((attempt + 1) * 2) + random.uniform(0, 1)
                print(f"Retrying stream in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)

xf_service = XFService()
