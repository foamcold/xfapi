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
from app.core.logger import logger

import os
import shutil

class XFService:
    AES_KEY = b'G%.g7"Y&Nf^40Ee<'
    SIGN_URL = "https://peiyin.xunfei.cn/web-server/1.0/works_synth_sign"
    SYNTH_URL_BASE = "https://peiyin.xunfei.cn/synth"
    CACHE_DIR = "data/cache"
    
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
        # 格式为：MD5(text + voice + speed + volume + pitch + type)
        raw = f"{text}_{voice_code}_{speed}_{volume}_{pitch}_{audio_type}"
        return hashlib.md5(raw.encode('utf-8')).hexdigest() + ("." + audio_type.split('/')[-1] if '/' in audio_type else ".mp3")

    def _clean_cache(self):
        limit = config.get_settings().get("cache_limit", 100)
        if limit <= 0:
            return

        # 确保cache目录存在
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)
            return

        files = [os.path.join(self.CACHE_DIR, f) for f in os.listdir(self.CACHE_DIR)]
        files = [f for f in files if os.path.isfile(f)]
        
        if len(files) > limit:
            # 按修改时间排序 (最早的在前)
            files.sort(key=os.path.getmtime)
            # 删除最早的文件
            for f in files[:len(files) - limit]:
                try:
                    os.remove(f)
                except Exception as e:
                    logger.error(f"清理缓存文件 {f} 时出错: {e}")

    async def _worker(self):
        while True:
            future, args = await self.queue.get()
            try:
                # 参数: (text, voice_code, speed, volume, pitch, audio_type)
                text, voice_code, speed, volume, pitch, audio_type = args
                
                url = self.get_audio_url(*args)
                resp = self.get_audio_stream(url)
                
                # 如果启用了缓存，则保存到缓存
                limit = config.get_settings().get("cache_limit", 100)
                if limit > 0:
                    # 确保cache目录存在
                    if not os.path.exists(self.CACHE_DIR):
                        os.makedirs(self.CACHE_DIR)
                    
                    cache_key = self._get_cache_key(*args)
                    cache_path = os.path.join(self.CACHE_DIR, cache_key)
                    
                    # 我们需要读取内容以保存它，但 resp 是一个流。
                    # 我们可以将流式传输到文件，然后为用户重新打开吗？
                    # 或者只是在迭代时保存块？
                    # 端点需要一个迭代器。
                    # 让我们先保存到临时文件，然后移动到缓存，然后从缓存提供服务？
                    # 或者只是将所有内容读入内存（可能会很大）？
                    # 更好的办法是：流式传输到文件，然后提供文件流。
                    
                    with open(cache_path, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=4096):
                            if chunk:
                                f.write(chunk)
                    
                    self._clean_cache()
                    
                    # 返回一个从文件读取的模拟响应
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
                
                # 成功生成后等待配置的延迟
                delay = config.get_settings().get("generation_interval", 1.0)
                await asyncio.sleep(float(delay))
                
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            finally:
                self.queue.task_done()

    async def process_tts_request(self, text: str, voice_code: str, speed: int, volume: int, pitch: int = 50, audio_type: str = "mp3"):
        # 首先检查缓存
        limit = config.get_settings().get("cache_limit", 100)
        if limit > 0:
            # 确保cache目录存在
            if not os.path.exists(self.CACHE_DIR):
                os.makedirs(self.CACHE_DIR)
            
            cache_key = self._get_cache_key(text, voice_code, speed, volume, pitch, audio_type)
            cache_path = os.path.join(self.CACHE_DIR, cache_key)
            
            if os.path.exists(cache_path):
                # 更新修改时间
                os.utime(cache_path, None)
                
                # 返回模拟响应
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
                
                # 立即返回，绕过队列
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
        # 音高标签: [te50]
        pitch_tag = f"[te{pitch}]" if pitch != 50 else "" # 假设 50 是默认/中性？插件提示：pitch ? '[te' + pitch + ']' : '';
        # 实际上，如果 pitch 为真，插件会发送它。如果 pitch 为 0 呢？
        # 让我们遵循插件的逻辑：pitch = pitch ? '[te' + pitch + ']' : '';
        # 但是我们传递的 pitch 是整数。如果 pitch 为 0，它会什么都不发送吗？
        # 让我们假设我们的音高 50 是标准的。
        # 插件逻辑：pitch = pitch ? ...
        # 如果我们传递了 pitch，我们应该添加它。
        pitch_tag = f"[te{pitch}]" if pitch is not None else ""
        
        # 情绪标签: [em{emo}:{emo_value}]
        emo_tag = f"[em{emo}:{emo_value}]" if emo else ""
        
        return f"{pitch_tag}{emo_tag}{text}"

    def get_audio_url(self, text: str, voice_code: str, speed: int, volume: int, pitch: int = 50, audio_type: str = "mp3") -> str:
        processed_text = self._process_special_symbols(text)
        
        # 处理自定义语音格式 (vid_emo)
        vid = voice_code
        emo = ""
        if "_" in voice_code:
            parts = voice_code.split("_")
            vid = parts[0]
            if len(parts) > 1:
                emo = parts[1]

        # 参数映射逻辑
        # 速度: 0-100 -> -200 到 200 (斜率 4)
        # 100-300 -> 200 到 500 (斜率 1.5)
        sp = int(speed)
        if sp <= 100:
            final_speed = sp * 4 - 200
        else:
            final_speed = int(200 + (sp - 100) * 1.5)
            
        final_volume = int(int(volume) * 0.4 - 20)
        
        # 将标签添加到文本中
        # 我们将 emo_value 默认设置为 0，因为我们还没有它的滑块
        tagged_text = self._process_text_tags(processed_text, pitch, emo, 0)
        
        # 计算哈希值
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
        
        # 带退避算法的重试循环
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
                logger.warning(f"签名URL请求尝试 {attempt + 1} 次失败: {e}")
                # 强制关闭会话以清除损坏的连接/SSL 状态
                self._close_session()
                
                if attempt == max_retries - 1:
                    logger.error("签名URL请求在多次重试后失败。")
                    raise
                
                # 线性退避，基数更高：2s, 4s, 6s, 8s, 10s... + 抖动
                sleep_time = ((attempt + 1) * 2) + random.uniform(0, 1)
                logger.info(f"将在 {sleep_time:.2f} 秒后重试...")
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
                # 为每次尝试创建一个新的会话，以确保没有过时的连接
                session = requests.Session()
                # 我们仍然可以在会话中使用 HTTPAdapter 进行标准重试，
                # 但外层循环处理“核选项”，即创建一个新的会话。
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
                logger.warning(f"音频流请求尝试 {attempt + 1} 次失败: {e}")
                
                if attempt == max_retries - 1:
                    logger.error("音频流请求在多次重试后失败。")
                    raise
                
                # 线性退避，基数更高：2s, 4s, 6s, 8s, 10s... + 抖动
                sleep_time = ((attempt + 1) * 2) + random.uniform(0, 1)
                logger.info(f"将在 {sleep_time:.2f} 秒后重试音频流...")
                time.sleep(sleep_time)

xf_service = XFService()
