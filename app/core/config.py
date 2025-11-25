import yaml
import os
from typing import List, Dict, Any
from app.core.logger import logger, set_log_level

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            # 不再自动加载配置，将其移至 lifespan 中手动调用
            # cls._instance.load_config()
            cls._instance.speakers = []
            cls._instance.settings = {}
        return cls._instance

    def load_config(self):
        self.speakers = []
        self.settings = {}

        # 为 Java 标签注册构造函数
        def speaker_constructor(loader, node):
            fields = loader.construct_mapping(node, deep=True)
            return fields

        yaml.add_constructor('tag:yaml.org,2002:org.nobody.multitts.tts.speaker.Speaker', speaker_constructor, Loader=yaml.SafeLoader)

        # 加载根目录下的 config.yaml
        try:
            with open("data/config.yaml", "r", encoding="utf-8") as f:
                root_config = yaml.safe_load(f)
                if root_config and "xfpeiyin" in root_config:
                    self.speakers.extend(root_config["xfpeiyin"])

        except FileNotFoundError:
            logger.warning("未找到配置文件 config.yaml。")
        except Exception as e:
            logger.error(f"加载 config.yaml 出错: {e}")

        # 加载 multitts/config.yaml
        try:
            with open("data/multitts/config.yaml", "r", encoding="utf-8") as f:
                multitts_config = yaml.safe_load(f)
                if multitts_config and "xfpeiyin" in multitts_config:
                    self.speakers.extend(multitts_config["xfpeiyin"])
        except FileNotFoundError:
            # 这是可选的扩展配置，找不到是正常行为，无需提示
            pass
        except Exception as e:
            logger.error(f"加载 multitts/config.yaml 出错: {e}")

        # 加载 settings.yaml
        if not os.path.exists("data/settings.yaml"):
            logger.info("未找到 settings.yaml。正在尝试从默认配置创建...")
            try:
                # 确保 data 目录存在
                if not os.path.exists("data"):
                    os.makedirs("data")
                    logger.info("已创建 data/ 目录。")

                if os.path.exists("data/settings.example.yaml"):
                    import shutil
                    shutil.copy("data/settings.example.yaml", "data/settings.yaml")
                    logger.info("已从 settings.example.yaml 创建 settings.yaml。")
                else:
                    # 创建默认设置
                    default_settings = {
                        "port": 8501,
                        "auth_enabled": False,
                        "admin_password": "admin",
                        "default_speaker": "聆小糖",
                        "default_speed": 100,
                        "default_volume": 100,
                        "cache_limit": 100,
                        "generation_interval": 1.0,
                        "default_audio_type": "audio/mp3",
                        "default_audio_type": "audio/mp3",
                        "special_symbol_mapping": False,
                        "log_level": "INFO"
                    }
                    with open("data/settings.yaml", "w", encoding="utf-8") as f:
                        yaml.dump(default_settings, f, allow_unicode=True, sort_keys=False)
                    logger.info("已创建默认的 settings.yaml。")
            except Exception as e:
                logger.error(f"创建 settings.yaml 时出错: {e}")

        try:
            with open("data/settings.yaml", "r", encoding="utf-8") as f:
                self.settings = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"加载 settings.yaml 时出错: {e}")
            self.settings = {}
            
        # 设置日志级别
        set_log_level(self.settings.get("log_level", "INFO"))

    def get_speakers(self) -> List[Dict[str, Any]]:
        return self.speakers

    def get_settings(self) -> Dict[str, Any]:
        return self.settings

    def update_setting(self, key: str, value: Any):
        self.settings[key] = value
        
        # 如果更新了日志级别，立即生效
        if key == "log_level":
            set_log_level(value)
        
        # 强制排序
        ordered_keys = [
            "port",
            "log_level",
            "auth_enabled",
            "admin_password",
            "default_speaker",
            "default_speed",
            "default_volume",
            "cache_limit",
            "generation_interval",
            "default_audio_type",
            "special_symbol_mapping"
        ]
        
        ordered_settings = {}
        # 按顺序添加键
        for k in ordered_keys:
            if k in self.settings:
                ordered_settings[k] = self.settings[k]
        
        # 添加任何剩余的键
        for k, v in self.settings.items():
            if k not in ordered_keys:
                ordered_settings[k] = v
                
        # 写入前确保目录存在
        settings_path = "data/settings.yaml"
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        
        with open(settings_path, "w", encoding="utf-8") as f:
            yaml.dump(ordered_settings, f, allow_unicode=True, sort_keys=False)

    def reload_config(self):
        self.load_config()

config = Config()
