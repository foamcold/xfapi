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

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置文件

复制 `settings.example.yaml` 为 `settings.yaml`：

```bash
cp settings.example.yaml settings.yaml
```

根据需要修改 `settings.yaml` 中的配置（如管理密码、默认发音人等）。

### 4. 启动服务

```bash
python main.py
```

服务默认运行在 `http://0.0.0.0:8000`。

## 使用说明

### Web 界面

访问 `http://localhost:8000` 即可进入 Web 界面进行语音合成测试。
访问 `http://localhost:8000/settings_page` 进入设置页面。

### API 文档

启动服务后，访问 `http://localhost:8000/docs` 查看完整的 Swagger API 文档。

### 核心接口

**GET /api/tts**

生成语音。

参数：
- `text`: 要转换的文本
- `voice_code`: 发音人代码 (默认: 聆小糖)
- `speed`: 语速 (0-300, 默认: 100)
- `volume`: 音量 (0-300, 默认: 100)
- `stream`: 是否流式返回 (默认: true)

示例：
```
http://localhost:8000/api/tts?text=你好世界&speed=100
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
