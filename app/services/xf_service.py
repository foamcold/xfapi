import json
import base64
import hashlib
import asyncio
import time
import random
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from urllib.parse import quote
from app.core.config import config
from app.core.logger import logger
from app.core.disguise import DisguiseClient

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
            # 记录从队列中获取任务的时间
            queue_wait_start = time.time()
            future, args = await self.queue.get()
            queue_wait_time = (time.time() - queue_wait_start) * 1000
            
            if queue_wait_time > 100:  # 超过100ms才记录
                logger.info(f"[TTS] 队列等待: {queue_wait_time:.0f}ms")
            
            try:
                # 记录整个TTS生成的开始时间
                tts_start = time.time()
                
                # 参数: (text, voice_code, speed, volume, pitch, audio_type)
                text, voice_code, speed, volume, pitch, audio_type = args
                
                # 步骤1: 获取签名URL
                step1_start = time.time()
                url = self.get_audio_url(*args)
                step1_time = (time.time() - step1_start) * 1000
                logger.info(f"[TTS] 步骤1-签名请求: {step1_time:.0f}ms")
                
                # 步骤2: 下载音频流
                step2_start = time.time()
                resp = self.get_audio_stream(url)
                step2_time = (time.time() - step2_start) * 1000
                logger.info(f"[TTS] 步骤2-音频下载: {step2_time:.0f}ms")
                
                # 如果启用了缓存，则保存到缓存
                limit = config.get_settings().get("cache_limit", 100)
                if limit > 0:
                    # 确保cache目录存在
                    if not os.path.exists(self.CACHE_DIR):
                        os.makedirs(self.CACHE_DIR)
                    
                    cache_key = self._get_cache_key(*args)
                    cache_path = os.path.join(self.CACHE_DIR, cache_key)
                    
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
                
                # 记录总耗时
                total_time = (time.time() - tts_start) * 1000
                if total_time > 10000:  # 超过10秒标记为WARNING
                    logger.warning(f"[TTS] 总耗时: {total_time:.0f}ms (步骤1: {step1_time:.0f}ms + 步骤2: {step2_time:.0f}ms)")
                else:
                    logger.info(f"[TTS] 总耗时: {total_time:.0f}ms")
                
                logger.debug(f"[TTS] 准备sleep({config.get_settings().get('generation_interval', 1.0)}s)")
                sleep_start = time.time()
                
                # 成功生成后等待配置的延迟
                delay = config.get_settings().get("generation_interval", 1.0)
                await asyncio.sleep(float(delay))
                
                sleep_time = (time.time() - sleep_start) * 1000
                logger.debug(f"[TTS] sleep完成: {sleep_time:.0f}ms")
                logger.debug(f"[TTS] worker准备好处理下一个请求")
                
            except Exception as e:
                logger.error(f"[TTS] 生成失败: {e}")
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

    def _get_disguise_client(self):
        """获取线程本地的伪装客户端"""
        if not hasattr(self._thread_local, "disguise_client"):
            self._thread_local.disguise_client = DisguiseClient(browser="chrome")
        return self._thread_local.disguise_client

    def _close_client(self):
        """关闭伪装客户端"""
        if hasattr(self._thread_local, "disguise_client"):
            try:
                self._thread_local.disguise_client.clear_cookies()
            except:
                pass
            del self._thread_local.disguise_client

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
        # 直接使用字典对象,让 curl_cffi 自动处理 JSON 序列化
        final_req = {"req": encrypted_req}
        
        # 带退避算法的重试循环
        max_retries = 5
        
        for attempt in range(max_retries):
            client = self._get_disguise_client()
            try:
                # 记录签名请求开始时间
                sign_start = time.time()
                
                # 使用伪装客户端发送POST请求,使用 json 参数而不是 data
                resp = client.post(
                    self.SIGN_URL, 
                    json=final_req,
                    request_type="api",
                    add_delay=True if attempt > 0 else False
                )
                resp.raise_for_status()
                
                # 记录签名请求耗时
                sign_elapsed = (time.time() - sign_start) * 1000
                if sign_elapsed > 5000:  # 如果超过5秒,记录警告
                    logger.warning(f"  └─ 签名请求耗时较长: {sign_elapsed:.0f}ms, 尝试: {attempt + 1}")
                elif sign_elapsed > 2000:  # 超过2秒记录INFO
                    logger.info(f"  └─ 签名请求: {sign_elapsed:.0f}ms, 尝试: {attempt + 1}")
                
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
                logger.warning(f"签名URL请求尝试 {attempt + 1}/{max_retries} 次失败: {e}")
                # 强制关闭客户端以清除损坏的连接/SSL 状态
                self._close_client()
                
                if attempt == max_retries - 1:
                    logger.error("签名URL请求在多次重试后失败。")
                    raise
                
                # 线性退避,基数更高:2s, 4s, 6s, 8s, 10s... + 抖动
                sleep_time = ((attempt + 1) * 2) + random.uniform(0, 1)
                logger.info(f"将在 {sleep_time:.2f} 秒后重试...")
                time.sleep(sleep_time)

    def get_audio_stream(self, url: str):
        """获取音频流
        
        Args:
            url: 音频URL
            
        Returns:
            响应对象(支持流式传输)
        """
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                # 记录音频流请求开始时间
                stream_start = time.time()
                
                # 为每次尝试创建一个新的伪装客户端
                client = DisguiseClient(browser="chrome")
                
                # 使用伪装客户端发送GET请求(流式传输)
                resp = client.get(
                    url, 
                    request_type="resource",
                    stream=True,
                    add_delay=True if attempt > 0 else False
                )
                resp.raise_for_status()
                
                # 记录音频流请求耗时
                stream_elapsed = (time.time() - stream_start) * 1000
                if stream_elapsed > 5000:  # 如果超过5秒,记录警告
                    logger.warning(f"  └─ 音频流耗时较长: {stream_elapsed:.0f}ms, 尝试: {attempt + 1}")
                elif stream_elapsed > 2000:  # 超过2秒记录INFO
                    logger.info(f"  └─ 音频流: {stream_elapsed:.0f}ms, 尝试: {attempt + 1}")
                
                return resp
                
            except Exception as e:
                logger.warning(f"音频流请求尝试 {attempt + 1}/{max_retries} 次失败: {e}")
                
                if attempt == max_retries - 1:
                    logger.error("音频流请求在多次重试后失败。")
                    raise
                
                # 线性退避,基数更高:2s, 4s, 6s, 8s, 10s... + 抖动
                sleep_time = ((attempt + 1) * 2) + random.uniform(0, 1)
                logger.info(f"将在 {sleep_time:.2f} 秒后重试音频流...")
                time.sleep(sleep_time)

xf_service = XFService()
