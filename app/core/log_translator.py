import logging

class UvicornLogTranslator(logging.Filter):
    """
    一个日志过滤器，用于将 Uvicorn 的英文日志翻译成中文。
    """
    STATIC_TRANSLATIONS = {
        "Started server process": "服务进程已启动",
        "Waiting for application startup.": "等待应用程序启动...",
        "Application startup complete.": "应用程序启动完成。",
        "Uvicorn running on": "Uvicorn 正在运行于",
        "Shutting down": "正在关闭服务...",
        "Waiting for application shutdown.": "等待应用程序关闭...",
        "Application shutdown complete.": "应用程序关闭完成。",
        "Finished server process": "服务进程已结束",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.error" and isinstance(record.msg, str):
            # 动态翻译：专门处理 "Cancel X running task(s)..."
            # 这种方法更健壮，不依赖于精确的字符串匹配
            if record.msg.startswith("Cancel ") and "running task(s)" in record.msg and record.args:
                try:
                    num_tasks = record.args[0]
                    record.msg = f"强制取消 {num_tasks} 个正在运行的超时任务。"
                    record.args = ()  # 清空参数，因为消息已手动格式化
                    return True  # 翻译完成，处理下一个记录
                except (IndexError, TypeError):
                    # 如果参数不符合预期，则不做任何事，让它按原样打印
                    pass

            # 静态翻译：处理其他固定的日志消息
            for original, translated in self.STATIC_TRANSLATIONS.items():
                if original in record.msg:
                    record.msg = record.msg.replace(original, translated)
                    break

        return True