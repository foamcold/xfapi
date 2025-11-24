# XFAPI - 讯飞配音逆向 API

XFAPI 是一个基于 FastAPI 构建的讯飞配音（peiyin.xunfei.cn）逆向 API 服务。它提供了一个简单的 HTTP 接口和 Web 管理界面，用于生成高质量的 TTS（语音合成）音频。

## 功能特点

- **API 代理**：封装讯飞配音网页版接口，支持多种发音人。
- **Web 界面**：内置美观的 Web 界面，支持在线试听、参数调整（语速、音量等）。
- **流式输出**：支持音频流式传输，响应速度快。
- **并发支持**：通过线程隔离和自动重试机制，支持高并发请求。
- **安全鉴权**：支持可选的登录鉴权功能，保护服务不被滥用。
- **配置管理**：支持通过 Web 界面动态修改默认参数和发音人配置。

## 安装与运行

### 1. 环境准备

确保已安装 Python 3.8+。

建议使用虚拟环境运行本项目，以避免依赖冲突：

**Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置文件

复制 `settings.example.yaml` 为 `settings.yaml`：

```bash
cp settings.example.yaml settings.yaml
```

根据需要修改 `settings.yaml` 中的配置（如管理密码、默认发音人、端口等）。

### 4. 启动服务

```bash
python main.py
```

服务默认运行在 `http://0.0.0.0:8501`（可在 `settings.yaml` 中修改）。

## 使用说明

### Web 界面

访问 `http://localhost:8501` 即可进入 Web 界面进行语音合成测试。
访问 `http://localhost:8501/settings_page` 进入设置页面。

### API 文档

启动服务后，访问 `http://localhost:8501/docs` 查看完整的 Swagger API 文档。

### 核心接口

**GET / POST /api/tts**

生成语音。

参数说明：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `text` | string | 是 | - | 要转换的文本内容 |
| `voice` | string | 否 | 聆小糖 | 发音人名称（如"聆小糖"）或发音人ID代码（如"565854553"）。后端会自动识别。 |
| `speed` | int | 否 | 100 | 语速，范围 0-300 |
| `volume` | int | 否 | 100 | 音量，范围 0-300 |
| `audio_type` | string | 否 | audio/mp3 | 音频格式，支持 `audio/mp3` 或 `audio/wav` |
| `stream` | boolean | 否 | true | 是否流式返回音频数据 |
| `key` | string | 否 | - | 鉴权密钥（如果开启了鉴权功能，则必填） |

**GET 请求示例：**

```
http://localhost:8501/api/tts?text=你好世界&voice=聆小糖&speed=100
```

**POST 请求示例：**

```json
POST /api/tts
Content-Type: application/json

{
    "text": "你好世界",
    "voice": "565854553",
    "speed": 100,
    "volume": 100,
    "audio_type": "audio/mp3",
    "stream": true,
    "key": "your_admin_password"
}
```

## 扩展发音人 (MultiTTS 兼容)

本项目完全兼容 MultiTTS 的数据格式。如果您需要使用更多发音人：

1.  请自行获取 **MultiTTS 讯飞配音插件**。
2.  将插件压缩包解压到项目multitts文件夹内，确保 `multitts` 文件夹位于根目录下（即 `xfapi/multitts/`）。
3.  重启服务，系统会自动扫描并加载 `multitts` 目录下的所有发音人配置及头像资源。

## 项目结构

```
xfapi/
├── app/
│   ├── api/                    # API 路由定义
│   ├── core/                   # 核心配置加载
│   └── services/               # 业务逻辑 (XFService)
├── static/                     # 静态资源 (CSS, JS, HTML)
├── config.yaml                 # 发音人列表配置
├── settings.yaml               # 系统设置 (自动生成/忽略)
├── multitts/                   # 包含发音人头像等资源 (可选)
├── multitts/config.yaml        # 发音人扩展 (可选)
├── multitts/xfpeiyin/avatar    # 发音人头像 (可选)
├── main.py                     # 程序入口
└── requirements.txt            # 项目依赖
```

## 注意事项

- 本项目仅供学习和研究使用，请勿用于商业用途。
- 请遵守讯飞配音的使用条款。

## 许可证

MIT License
