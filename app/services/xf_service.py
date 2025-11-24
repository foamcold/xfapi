import json
import base64
import hashlib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from urllib.parse import quote
from app.core.config import config

class XFService:
    AES_KEY = b'G%.g7"Y&Nf^40Ee<'
    SIGN_URL = "https://peiyin.xunfei.cn/web-server/1.0/works_synth_sign"
    SYNTH_URL_BASE = "https://peiyin.xunfei.cn/synth"
    
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
        
        # Calculate hash
        txt = processed_text
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
