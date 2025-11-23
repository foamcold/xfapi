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
            self._thread_local.session = self._create_session()
        return self._thread_local.session

    def _create_session(self):
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _reset_session(self):
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

        # Parameter mapping logic from JS plugin
        # speed: 0-300 -> mapped to -500 to 500 range in some implementations, but JS says: speed = speed * 4 - 200
        # Wait, JS logic: speed = speed * 4 - 200. Input speed 0-100?
        # User requirement: speed 0-300, default 100.
        # Let's follow the JS logic exactly if possible, or adapt.
        # JS: speed = speed * 4 - 200. If input is 100, result is 200.
        # If input is 50, result is 0.
        # The user said speed 0-300.
        # Let's use the formula: speed_val = speed * 4 - 200.
        # If user sends 100 (default), val = 200.
        # If user sends 300, val = 1000.
        # If user sends 0, val = -200.
        
        # Volume: JS says volume = Math.floor(volume * 0.4 - 20)
        # User input 0-300. Default 100.
        # If 100 -> 20.
        
        # Pitch: JS says pitch = pitch ? '[te' + pitch + ']' : ''
        
        # Emo and Sound Effect logic
        # For now, we'll stick to basic params.
        
        # Construct text with tags
        # pitch_tag = f"[te{pitch}]" if pitch != 50 else "" # Assuming 50 is default/neutral
        # JS Plugin logic for pitch: pitch = pitch ? '[te' + pitch + ']' : '';
        # We will omit pitch for now as it's not in the primary requirements list, but good to have.
        
        # Calculate hash
        # txt = effectTag + pitch + emo + processed_text
        # For simplicity, just processed_text for now unless we add more features.
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
            # 'Connection': 'close' # Removed to allow keep-alive with session
        }
        
        # Manual retry loop with session reset
        import time
        max_retries = 3
        
        for attempt in range(max_retries):
            session = self._get_session()
            try:
                resp = session.post(self.SIGN_URL, data=final_req, headers=headers, timeout=10)
                resp.raise_for_status()
                
                resp_json = resp.json()
                
                if "body" not in resp_json:
                     raise Exception(f"Unexpected response format: {resp_json}")

                decrypted_body = self._decrypt(resp_json["body"])
                # decrypted_body is a dict like {"time_stamp": "...", "sign_text": "..."}
                
                # Construct final URL
                # Apply transforms
                # Piecewise function for speed to support 0-300 range without hitting API limit (approx 500)
                # 0-100 maps to -200 to 200 (Slope 4) - Preserves original behavior
                # 100-300 maps to 200 to 500 (Slope 1.5) - Compresses high range to fit
                sp = int(speed)
                if sp <= 100:
                    final_speed = sp * 4 - 200
                else:
                    final_speed = int(200 + (sp - 100) * 1.5)
                    
                final_volume = int(int(volume) * 0.4 - 20)
                
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

            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                print(f"Attempt {attempt + 1} failed with SSL/Connection error: {e}")
                # Reset session to clear broken connection
                self._reset_session()
                
                if attempt == max_retries - 1:
                    raise
                time.sleep(1) # Wait 1 second before retrying
            except Exception as e:
                print(f"Error getting audio URL: {e}")
                raise

    def get_audio_stream(self, url: str):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://peiyin.xunfei.cn/',
            'Connection': 'close'
        }
        # Use a fresh session/request for streaming to avoid blocking the thread-local session pool
        # and to ensure isolation for long-running downloads.
        return requests.get(url, headers=headers, stream=True, timeout=30)

xf_service = XFService()
