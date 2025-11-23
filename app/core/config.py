import yaml
import os
from typing import List, Dict, Any

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        self.speakers = []
        self.settings = {}

        # Register constructor for Java tag
        def speaker_constructor(loader, node):
            fields = loader.construct_mapping(node, deep=True)
            return fields

        yaml.add_constructor('tag:yaml.org,2002:org.nobody.multitts.tts.speaker.Speaker', speaker_constructor, Loader=yaml.SafeLoader)

        # Load root config.yaml
        try:
            with open("config.yaml", "r", encoding="utf-8") as f:
                root_config = yaml.safe_load(f)
                if root_config and "xfpeiyin" in root_config:
                    self.speakers.extend(root_config["xfpeiyin"])
        except FileNotFoundError:
            print("Warning: config.yaml not found.")
        except Exception as e:
            print(f"Error loading config.yaml: {e}")

        # Load multitts/config.yaml
        try:
            with open("multitts/config.yaml", "r", encoding="utf-8") as f:
                multitts_config = yaml.safe_load(f)
                if multitts_config and "xfpeiyin" in multitts_config:
                    self.speakers.extend(multitts_config["xfpeiyin"])
        except FileNotFoundError:
            print("Warning: multitts/config.yaml not found.")
        except Exception as e:
            print(f"Error loading multitts/config.yaml: {e}")

        # Load settings.yaml
        try:
            with open("settings.yaml", "r", encoding="utf-8") as f:
                self.settings = yaml.safe_load(f) or {}
        except FileNotFoundError:
            print("Warning: settings.yaml not found. Using defaults.")
            self.settings = {}
        except Exception as e:
            print(f"Error loading settings.yaml: {e}")

    def get_speakers(self) -> List[Dict[str, Any]]:
        return self.speakers

    def get_settings(self) -> Dict[str, Any]:
        return self.settings

    def update_setting(self, key: str, value: Any):
        self.settings[key] = value
        with open("settings.yaml", "w", encoding="utf-8") as f:
            yaml.dump(self.settings, f, allow_unicode=True)

config = Config()
