"""
伪装访问模块

提供浏览器指纹伪装功能,包括:
- User-Agent 伪装
- 完整请求头伪装
- Referer 头部伪装
- TLS/HTTP/2 指纹伪装
- Cookie 管理
- 其他高级伪装功能
"""

import random
import time
from typing import Optional, Dict, Any
from curl_cffi import requests as curl_requests
from fake_useragent import UserAgent
from app.core.logger import logger


class DisguiseClient:
    """伪装访问客户端,提供浏览器指纹伪装功能"""
    
    # 浏览器版本映射 (用于 curl_cffi 的 impersonate 参数)
    BROWSER_VERSIONS = {
        "chrome": ["chrome110", "chrome107", "chrome104", "chrome101", "chrome100", "chrome99"],
        "edge": ["edge101", "edge99"],
        "firefox": ["firefox109", "firefox108", "firefox102"],
        "safari": ["safari15_5", "safari15_3"]
    }
    
    def __init__(self, browser: str = "chrome", version: Optional[str] = None, 
                 enable_http2: bool = True, timeout: int = 30):
        """初始化伪装客户端
        
        Args:
            browser: 浏览器类型 (chrome/edge/firefox/safari)
            version: 浏览器版本 (如果为None,则随机选择)
            enable_http2: 是否启用 HTTP/2
            timeout: 请求超时时间(秒)
        """
        self.browser = browser.lower()
        self.timeout = timeout
        self.enable_http2 = enable_http2
        
        # 选择浏览器版本用于 impersonate
        if version:
            self.impersonate = version
        else:
            # 从可用版本中随机选择
            if self.browser in self.BROWSER_VERSIONS:
                self.impersonate = random.choice(self.BROWSER_VERSIONS[self.browser])
            else:
                # 默认使用 Chrome
                self.impersonate = random.choice(self.BROWSER_VERSIONS["chrome"])
        
        # 初始化 User-Agent 生成器
        self.ua = UserAgent()
        
        # Cookie 存储
        self.cookies = {}
        
        logger.info(f"伪装客户端初始化: 浏览器={self.browser}, 版本={self.impersonate}")
    
    def _get_base_headers(self, url: str) -> Dict[str, str]:
        """获取基础请求头
        
        Args:
            url: 请求URL
            
        Returns:
            基础请求头字典
        """
        # 根据浏览器类型生成 User-Agent
        if self.browser == "chrome":
            user_agent = self.ua.chrome
        elif self.browser == "firefox":
            user_agent = self.ua.firefox
        elif self.browser == "edge":
            # Edge 使用 Chrome UA (因为 Edge 基于 Chromium)
            user_agent = self.ua.chrome.replace("Chrome", "Edg")
        elif self.browser == "safari":
            user_agent = self.ua.safari
        else:
            user_agent = self.ua.random
        
        # 基础请求头
        headers = {
            "User-Agent": user_agent,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Chrome 特有的客户端提示 (Client Hints)
        if self.browser in ["chrome", "edge"]:
            headers.update({
                "Sec-Ch-Ua": '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            })
        
        return headers
    
    def get_headers(self, url: str, request_type: str = "api", 
                   referer: Optional[str] = None, content_type: Optional[str] = None) -> Dict[str, str]:
        """获取完整的伪装请求头
        
        Args:
            url: 请求URL
            request_type: 请求类型 (api/page/resource)
            referer: 自定义 Referer (如果为None,则自动生成)
            content_type: Content-Type (用于POST请求)
            
        Returns:
            完整的伪装请求头字典
        """
        headers = self._get_base_headers(url)
        
        # 根据请求类型设置不同的 Accept 头
        if request_type == "api":
            headers["Accept"] = "application/json, text/plain, */*"
        elif request_type == "page":
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
        elif request_type == "resource":
            headers["Accept"] = "*/*"
        
        # 设置 Referer
        if referer:
            headers["Referer"] = referer
        elif "xunfei.cn" in url:
            # 讯飞相关请求,设置为讯飞配音首页
            headers["Referer"] = "https://peiyin.xunfei.cn/"
            headers["Origin"] = "https://peiyin.xunfei.cn"
        
        # 设置 Content-Type (用于POST请求)
        if content_type:
            headers["Content-Type"] = content_type
        
        # 添加安全策略头 (Chrome/Edge)
        if self.browser in ["chrome", "edge"]:
            if request_type == "api":
                headers.update({
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                })
            elif request_type == "page":
                headers.update({
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                })
        
        return headers
    
    def _add_random_delay(self, min_delay: float = 0.1, max_delay: float = 0.5):
        """添加随机延迟,模拟人类行为
        
        Args:
            min_delay: 最小延迟(秒)
            max_delay: 最大延迟(秒)
        """
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def post(self, url: str, data=None, json=None, headers: Optional[Dict[str, str]] = None,
             request_type: str = "api", add_delay: bool = False, **kwargs) -> Any:
        """发送 POST 请求
        
        Args:
            url: 请求URL
            data: 表单数据
            json: JSON数据
            headers: 自定义请求头 (会与伪装头合并)
            request_type: 请求类型
            add_delay: 是否添加随机延迟
            **kwargs: 其他传递给 curl_cffi 的参数
            
        Returns:
            响应对象
        """
        # 获取伪装请求头
        content_type = None
        if json is not None:
            content_type = "application/json;charset=UTF-8"
        elif data is not None:
            content_type = "application/x-www-form-urlencoded"
        
        disguise_headers = self.get_headers(url, request_type, content_type=content_type)
        
        # 合并自定义请求头
        if headers:
            disguise_headers.update(headers)
        
        # 添加随机延迟
        if add_delay:
            self._add_random_delay()
        
        # 发送请求 (使用 impersonate 进行 TLS/HTTP/2 指纹伪装)
        try:
            response = curl_requests.post(
                url,
                data=data,
                json=json,
                headers=disguise_headers,
                cookies=self.cookies,
                timeout=self.timeout,
                impersonate=self.impersonate,
                **kwargs
            )
            
            # 更新 cookies
            if response.cookies:
                self.cookies.update(response.cookies)
            
            return response
        except Exception as e:
            logger.error(f"POST 请求失败: {url}, 错误: {e}")
            raise
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None,
            request_type: str = "resource", stream: bool = False, 
            add_delay: bool = False, **kwargs) -> Any:
        """发送 GET 请求
        
        Args:
            url: 请求URL
            headers: 自定义请求头 (会与伪装头合并)
            request_type: 请求类型
            stream: 是否流式传输
            add_delay: 是否添加随机延迟
            **kwargs: 其他传递给 curl_cffi 的参数
            
        Returns:
            响应对象
        """
        # 获取伪装请求头
        disguise_headers = self.get_headers(url, request_type)
        
        # 合并自定义请求头
        if headers:
            disguise_headers.update(headers)
        
        # 添加随机延迟
        if add_delay:
            self._add_random_delay()
        
        # 发送请求 (使用 impersonate 进行 TLS/HTTP/2 指纹伪装)
        try:
            response = curl_requests.get(
                url,
                headers=disguise_headers,
                cookies=self.cookies,
                timeout=self.timeout,
                stream=stream,
                impersonate=self.impersonate,
                **kwargs
            )
            
            # 更新 cookies
            if response.cookies:
                self.cookies.update(response.cookies)
            
            return response
        except Exception as e:
            logger.error(f"GET 请求失败: {url}, 错误: {e}")
            raise
    
    def clear_cookies(self):
        """清除所有 cookies"""
        self.cookies.clear()
        logger.info("已清除所有 cookies")


# 创建默认伪装客户端实例
default_client = DisguiseClient()


def create_client(browser: str = "chrome", version: Optional[str] = None, **kwargs) -> DisguiseClient:
    """创建新的伪装客户端实例
    
    Args:
        browser: 浏览器类型
        version: 浏览器版本
        **kwargs: 其他参数
        
    Returns:
        DisguiseClient 实例
    """
    return DisguiseClient(browser=browser, version=version, **kwargs)
