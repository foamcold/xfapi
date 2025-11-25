# XFAPI - 讯飞配音逆向 API

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-supported-blue)

XFAPI 是一个基于 FastAPI 构建的讯飞配音（peiyin.xunfei.cn）逆向 API 服务。它提供了一个简单的 HTTP 接口和 Web 管理界面，用于生成高质量的 TTS（语音合成）音频。

## ✨ 功能特点

- **API 代理**：封装讯飞配音网页版接口，支持多种发音人。
- **Web 界面**：内置美观的 Web 界面，支持在线试听、参数调整（语速、音量等）。
- **流式输出**：支持音频流式传输，响应速度快。
- **并发支持**：通过线程隔离和自动重试机制，支持高并发请求。
- **安全鉴权**：支持可选的登录鉴权功能，保护服务不被滥用。
- **配置管理**：支持通过 Web 界面动态修改默认参数和发音人配置。

## 🚀 部署指南 / Deployment

本项目支持多种部署方式，请根据您的需求选择。

### 方式一：Docker 部署 (推荐)

Docker 部署是最简单且推荐的方式，支持一键启动。

#### 1. 生产模式 (Production)
适用于服务器部署，默认开启健康检查、非 root 用户运行，使用 Gunicorn 作为高性能服务器。

**使用 Docker Compose (推荐):**
```bash
# 1. 复制配置文件
cp data/settings.example.yaml data/settings.yaml

# 2. 启动服务 (后台运行)
docker-compose up -d
```

**手动构建运行:**
```bash
# 构建镜像
docker build -t xfapi .

# 运行容器
docker run -d \
  -p 8501:8501 \
  --name xfapi \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  xfapi
```

#### 2. 开发模式 (Development)
适用于开发调试，支持代码热重载 (Hot Reload)。

修改 `docker-compose.yml`，覆盖启动命令：
```yaml
services:
  xfapi:
    # ... 其他配置 ...
    command: python main.py  # 覆盖默认的 gunicorn 命令以启用 reload
    volumes:
      - .:/app  # 挂载当前目录以实时同步代码更改
```

---

### 方式二：标准部署 (Standard)

适用于本地运行或不支持 Docker 的环境。

#### 1. 环境准备
- Python 3.9+
- 建议使用虚拟环境

```bash
# 创建并激活虚拟环境
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置文件
```bash
cp data/settings.example.yaml data/settings.yaml
# 根据需要修改 data/settings.yaml
```

#### 3. 启动服务

**开发模式 (Development):**
内置自动重载功能，适合开发调试。
```bash
python main.py
```

**生产模式 (Production):**
使用高性能应用服务器启动。

*   **Linux/macOS:**
    ```bash
    # 使用 Gunicorn 管理 Uvicorn worker
    gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8501 main:app
    ```

*   **Windows:**
    ```bash
    # Windows 不支持 Gunicorn，直接使用 Uvicorn 多进程模式
    uvicorn main:app --host 0.0.0.0 --port 8501 --workers 4
    ```

访问 `http://localhost:8501` 即可进入 Web 界面。
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

```text
http://localhost:8501/api/tts?text=你好世界&voice=聆小糖&speed=100
```

**POST 请求示例 (cURL)：**

```bash
curl -X POST "http://localhost:8501/api/tts" \
     -H "Content-Type: application/json" \
     -d '{
           "text": "你好世界",
           "voice": "565854553",
           "speed": 100,
           "volume": 100,
           "audio_type": "audio/mp3",
           "stream": true
         }'
```

**POST 请求示例 (Raw HTTP)：**

```http
POST /api/tts HTTP/1.1
Host: localhost:8501
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

## 🔌 扩展发音人 (MultiTTS 兼容)

本项目完全兼容 MultiTTS 的数据格式。如果您需要使用更多发音人：

1.  请自行获取 **MultiTTS 讯飞配音插件**。
2.  将插件压缩包解压到项目 `data/multitts` 文件夹内，确保 `multitts` 文件夹位于 `data` 目录下（即 `xfapi/data/multitts/`）。
3.  重启服务，系统会自动扫描并加载 `data/multitts` 目录下的所有发音人配置及头像资源。

## 📂 项目结构

```
xfapi/
├── app/
│   ├── api/                    # API 路由定义
│   ├── core/                   # 核心配置加载
│   └── services/               # 业务逻辑 (XFService)
├── static/                     # 静态资源 (CSS, JS, HTML)
├── data/                       # 数据目录
│   ├── config.yaml             # 发音人列表配置
│   ├── settings.yaml           # 系统设置 (自动生成/忽略)
│   ├── cache/                  # 音频缓存
│   └── multitts/               # 包含发音人头像等资源 (可选)
│       ├── config.yaml         # 发音人扩展 (可选)
│       └── xfpeiyin/avatar/    # 发音人头像 (可选)
├── main.py                     # 程序入口
├── requirements.txt            # 项目依赖
├── Dockerfile                  # Docker 构建文件
└── docker-compose.yml          # Docker Compose 配置
```

## ⚠️ 注意事项

- 本项目仅供学习和研究使用，请勿用于商业用途。
- 请遵守讯飞配音的使用条款。

## 📜 许可证

MIT License
