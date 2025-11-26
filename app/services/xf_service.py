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
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

    def _get_cache_key(self, text: str, voice_code: str, speed: int, volume: int, pitch: int, audio_type: str) -> str:
        """生成缓存键"""
        raw = f"{text}_{voice_code}_{speed}_{volume}_{pitch}_{audio_type}"
        return hashlib.md5(raw.encode('utf-8')).hexdigest() + ("." + audio_type.split('/')[-1] if '/' in audio_type else ".mp3")

    def _clean_cache(self):
        """清理超出限制的缓存文件"""
        limit = config.get_settings().get("cache_limit", 100)
        if limit <= 0:
            return

        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)
            return

        files = [os.path.join(self.CACHE_DIR, f) for f in os.listdir(self.CACHE_DIR)]
        files = [f for f in files if os.path.isfile(f)]
        
        if len(files) > limit:
            files.sort(key=os.path.getmtime)
            for f in files[:len(files) - limit]:
                try:
                    os.remove(f)
                except Exception as e:
                    logger.error(f"清理缓存文件 {f} 时出错: {e}")

    class CachedStreamResponse:
        def __init__(self, response, cache_path, service):
            self.response = response
            self.cache_path = cache_path
            self.service = service

        def iter_content(self, chunk_size=4096):
            # 使用临时文件避免写入未完成的文件被读取
            temp_path = f"{self.cache_path}.{str(time.time())}.tmp"
            try:
                with open(temp_path, 'wb') as f:
                    for chunk in self.response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            yield chunk
                
                # 下载完成后重命名
                if os.path.exists(temp_path):
                    # 再次检查目标是否存在
                    if not os.path.exists(self.cache_path):
                        os.rename(temp_path, self.cache_path)
                        self.service._clean_cache()
                        logger.debug(f"[缓存] 已保存: {os.path.basename(self.cache_path)}")
                    else:
                        os.remove(temp_path)
            except Exception as e:
                logger.error(f"流式缓存出错: {e}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise

    async def process_tts_request(self, text: str, voice_code: str, speed: int, volume: int, pitch: int = 50, audio_type: str = "mp3"):
        """处理TTS请求 - 完全并发,无队列"""
        tts_start = time.time()
        
        # 检查缓存
        limit = config.get_settings().get("cache_limit", 100)
        if limit > 0:
            if not os.path.exists(self.CACHE_DIR):
                os.makedirs(self.CACHE_DIR)
            
            cache_key = self._get_cache_key(text, voice_code, speed, volume, pitch, audio_type)
            cache_path = os.path.join(self.CACHE_DIR, cache_key)
            
            if os.path.exists(cache_path):
                # 更新修改时间
                os.utime(cache_path, None)
                
                # 返回文件响应
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
                
                cache_time = (time.time() - tts_start) * 1000
                logger.info(f"[TTS] 缓存命中: {cache_time:.0f}ms")
                return FileStreamResponse(cache_path)
        
        # 为本次请求创建一个随机的伪装客户端(步骤1和步骤2共用)
        # 增加超时时间到120秒，防止长文本生成时截断
        client = DisguiseClient(browser="chrome", timeout=120)
        
        # 步骤1: 获取签名URL (在线程池中执行)
        step1_start = time.time()
        url = await asyncio.to_thread(self.get_audio_url, text, voice_code, speed, volume, pitch, audio_type, client)
        step1_time = (time.time() - step1_start) * 1000
        logger.info(f"[TTS] 步骤1-签名请求: {step1_time:.0f}ms")
        
        # 步骤2: 下载音频流 (在线程池中执行，使用相同的客户端)
        step2_start = time.time()
        resp = await asyncio.to_thread(self.get_audio_stream, url, client)
        step2_time = (time.time() - step2_start) * 1000
        logger.info(f"[TTS] 步骤2-音频下载: {step2_time:.0f}ms")
        
        # 记录总耗时
        total_time = (time.time() - tts_start) * 1000
        if total_time > 10000:
            logger.warning(f"[TTS] 总耗时: {total_time:.0f}ms (步骤1: {step1_time:.0f}ms + 步骤2: {step2_time:.0f}ms)")
        else:
            logger.info(f"[TTS] 总耗时: {total_time:.0f}ms")
        
        # 如果启用缓存,使用包装类进行流式保存
        if limit > 0:
            cache_key = self._get_cache_key(text, voice_code, speed, volume, pitch, audio_type)
            cache_path = os.path.join(self.CACHE_DIR, cache_key)
            return self.CachedStreamResponse(resp, cache_path, self)
        
        return resp



    def _process_special_symbols(self, text: str) -> str:
        """处理特殊符号映射"""
        if not config.get_settings().get("special_symbol_mapping", False):
            return text
        
        processed_text = ""
        for char in text:
            processed_text += self.SPECIAL_SYMBOLS_MAP.get(char, char)
        return processed_text

    def _encrypt(self, data: dict) -> str:
        """加密数据"""
        cipher = AES.new(self.AES_KEY, AES.MODE_ECB)
        json_str = json.dumps(data)
        encrypted_bytes = cipher.encrypt(pad(json_str.encode('utf-8'), AES.block_size))
        return base64.b64encode(encrypted_bytes).decode('utf-8')

    def _decrypt(self, encrypted_str: str) -> dict:
        """解密数据"""
        cipher = AES.new(self.AES_KEY, AES.MODE_ECB)
        encrypted_bytes = base64.b64decode(encrypted_str)
        decrypted_bytes = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
        return json.loads(decrypted_bytes.decode('utf-8'))

    def _process_text_tags(self, text: str, pitch: int, emo: str, emo_value: int = 0) -> str:
        """处理文本标签"""
        pitch_tag = f"[te{pitch}]" if pitch is not None else ""
        emo_tag = f"[em{emo}:{emo_value}]" if emo else ""
        return f"{pitch_tag}{emo_tag}{text}"

    def get_audio_url(self, text: str, voice_code: str, speed: int, volume: int, pitch: int = 50, audio_type: str = "mp3", client: DisguiseClient = None) -> str:
        """获取音频URL(同步方法)"""
        processed_text = self._process_special_symbols(text)
        
        # 处理自定义语音格式
        vid = voice_code
        emo = ""
        if "_" in voice_code:
            parts = voice_code.split("_")
            vid = parts[0]
            if len(parts) > 1:
                emo = parts[1]

        # 参数映射
        sp = int(speed)
        if sp <= 100:
            final_speed = sp * 4 - 200
        else:
            final_speed = int(200 + (sp - 100) * 1.5)
            
        final_volume = int(int(volume) * 0.4 - 20)
        
        tagged_text = self._process_text_tags(processed_text, pitch, emo, 0)
        
        # 计算哈希
        m = hashlib.md5()
        m.update(tagged_text.encode('utf-8'))
        txt_hash = m.hexdigest()
        
        req_data = {"synth_text_hash_code": txt_hash}
        encrypted_req = self._encrypt(req_data)
        final_req = {"req": encrypted_req}
        
        # 如果没有传入客户端，创建一个新的
        if client is None:
            client = DisguiseClient(browser="chrome", timeout=120)
        
        # 重试循环
        max_retries = 5
        for attempt in range(max_retries):
            try:
                resp = client.post(
                    self.SIGN_URL, 
                    json=final_req,
                    request_type="api",
                    add_delay=True if attempt > 0 else False
                )
                resp.raise_for_status()
                
                resp_json = resp.json()
                
                if "body" not in resp_json:
                     raise Exception(f"Unexpected response format: {resp_json}")

                decrypted_body = self._decrypt(resp_json["body"])
                
                txt_cnt = quote(tagged_text)
                
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
                
                if attempt == max_retries - 1:
                    logger.error("签名URL请求在多次重试后失败。")
                    raise
                
                sleep_time = ((attempt + 1) * 2) + random.uniform(0, 1)
                logger.info(f"将在 {sleep_time:.2f} 秒后重试...")
                time.sleep(sleep_time)

    def get_audio_stream(self, url: str, client: DisguiseClient = None):
        """获取音频流(同步方法)"""
        # 如果没有传入客户端，创建一个新的
        if client is None:
            client = DisguiseClient(browser="chrome", timeout=120)
        
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                
                resp = client.get(
                    url, 
                    request_type="resource",
                    stream=True,
                    add_delay=True if attempt > 0 else False
                )
                resp.raise_for_status()
                return resp
                
            except Exception as e:
                logger.warning(f"音频流请求尝试 {attempt + 1}/{max_retries} 次失败: {e}")
                
                if attempt == max_retries - 1:
                    logger.error("音频流请求在多次重试后失败。")
                    raise
                
                sleep_time = ((attempt + 1) * 2) + random.uniform(0, 1)
                logger.info(f"将在 {sleep_time:.2f} 秒后重试音频流...")
                time.sleep(sleep_time)

xf_service = XFService()
