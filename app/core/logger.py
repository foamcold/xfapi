import logging
import sys
import logging.handlers
from collections import deque
from colorama import Fore, Style, init

# 初始化 colorama
# 初始化 colorama
# init(autoreset=True)  # 移除此行以修复 Ctrl+C 无法退出的问题


class ColoredFormatter(logging.Formatter):
    """
    一个带有颜色的日志格式化器，可以根据日志级别显示不同的颜色。
    """
    LOG_COLORS = {
        logging.DEBUG: Style.DIM + Fore.WHITE,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Style.BRIGHT + Fore.RED,
    }

    def format(self, record):
        log_color = self.LOG_COLORS.get(record.levelno)
        
        # 设置基础格式
        # [时间] | [级别] | 消息
        # 使用 '{' 风格的格式化，它支持更丰富的对齐选项
        base_format = f"{Style.DIM + Fore.CYAN}{{asctime}}{Style.RESET_ALL} | " \
                      f"{log_color}{{levelname:^9}}{Style.RESET_ALL} | " \
                      f"{log_color}{{message}}{Style.RESET_ALL}"
        
        formatter = logging.Formatter(base_format, datefmt='%Y-%m-%d %H:%M:%S', style='{')
        
        # 对齐处理：INFO 级别前的空格
        if record.levelno == logging.INFO:
            # 获取当前格式化后的消息
            original_message = super().format(record)
            # 为了对齐，我们可以在这里调整，但由于levelname已经左对齐，所以通常不需要额外处理
            # 这里主要是为了演示如何处理特殊情况
            pass

        return formatter.format(record)

import asyncio

class LogQueue:
    def __init__(self, maxlen=2000):
        self._history = deque(maxlen=maxlen)
        self._subscribers = set()

    def append(self, record):
        self._history.append(record)
        for queue in self._subscribers:
            # 使用 put_nowait 是因为我们不希望日志记录器阻塞
            # 如果队列满了，它会引发异常，但这在 asyncio.Queue 中很少见
            queue.put_nowait(record)

    def subscribe(self, queue: asyncio.Queue):
        self._subscribers.add(queue)

    def unsubscribe(self, queue: asyncio.Queue):
        self._subscribers.discard(queue)

    def __iter__(self):
        return iter(self._history)

    def __len__(self):
        return len(self._history)

# 用于存储日志记录的内存队列
log_queue = LogQueue(maxlen=2000)

class QueueHandler(logging.Handler):
    """
    一个将日志记录放入我们自定义 LogQueue 的处理器。
    """
    def __init__(self, log_queue_instance: LogQueue):
        super().__init__()
        self.log_queue = log_queue_instance

    def emit(self, record):
        self.log_queue.append(self.format(record))

def setup_logger():
    """
    配置并获取根日志记录器。
    这个函数应该在应用程序启动时只调用一次。
    """
    # 获取根 logger
    logger = logging.getLogger()
    
    # 检查是否已经有处理器，防止重复添加
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(logging.DEBUG)

    # 1. 控制台处理器 (带颜色)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    # 2. 内存队列处理器 (用于Web界面)
    # 我们需要一个不带颜色的格式化器给Web界面
    # web_formatter = logging.Formatter(
    #     '{asctime} | {levelname:^9} | {message}',
    #     datefmt='%Y-%m-%d %H:%M:%S',
    #     style='{'
    # )
    queue_handler = QueueHandler(log_queue)
    # 使用带颜色的格式化器，以便前端可以解析
    queue_handler.setFormatter(ColoredFormatter())
    logger.addHandler(queue_handler)
    
    # 禁用 uvicorn 的默认访问日志，因为我们将使用自己的格式
    # logging.getLogger("uvicorn.access").propagate = False
    # logging.getLogger("uvicorn.error").propagate = False
    # logging.getLogger("uvicorn").propagate = False


# 在模块加载时就获取一个 logger 实例，以便其他模块可以直接导入使用
# setup_logger() 将在 main.py 中被显式调用
logger = logging.getLogger("XFAPI")

def set_log_level(level_name: str):
    """
    设置日志级别
    
    Args:
        level_name: 日志级别名称 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(level)
    # 同时更新 handler 的级别，确保一致性
    for handler in logger.handlers:
        handler.setLevel(level)

