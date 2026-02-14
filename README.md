# YouTube Transcript Automation Tool 🚀

这是一个自动化工具，旨在从 YouTube 获取字幕并同步到 Google Sheets。它采用“API 优先，AI 补位”的策略，确保即使视频没有提供官方字幕，也能通过语音识别（ASR）获取内容。

## 🌟 核心特性

-   **智能同步**：自动读取 Google Sheets 中的 YouTube URL，抓取字幕后写回。
-   **双重抓取机制**：
    -   **Level 1 (API)**：利用 `youtube-transcript-api` 秒抓官方或自动生成的字幕。
    -   **Level 2 (AI)**：若无字幕，自动调用 `yt-dlp` 下载音频并启用 `Faster-Whisper` 模型进行本地语音转文字。
-   **云端 ARCHIVE**：自动将转录所需的音频文件上传至 **Google Drive**，无需占用 VPS 本地空间。
-   **极速识别**：针对 VPS CPU 优化的 `Faster-Whisper`（默认使用 `base` 精度和 `int8` 量化）。

## 🛠️ 环境要求

-   Python 3.8+
-   **FFmpeg** (必须安装，用于音频提取)
-   Google Cloud 服务账号凭据 (`credentials.json`)

## 📦 快速开始

### 1. 安装依赖

```bash
pip install youtube-transcript-api gspread oauth2client yt-dlp faster-whisper google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 2. Google 项目配置

1.  在 [Google Cloud Console](https://console.cloud.google.com/) 创建项目并下载服务账号密钥，重命名为 `credentials.json` 放入根目录。
2.  开启以下 API 服务：
    -   Google Sheets API
    -   Google Drive API
3.  **共享权限**：
    -   将你的 Google Sheet 共享给服务账号的 Email（编辑器权限）。
    -   （可选）在 Drive 中创建一个文件夹，也共享给该 Email，以存储存档音频。

### 3. 配置脚本

项目支持使用 `.env` 文件管理配置。你可以直接修改根目录下的 `.env` 文件（或参考 `.env.example`）：

```env
# Google Cloud 凭据文件路径
CREDENTIALS_FILE=credentials.json

# 表格配置
SPREADSHEET_NAME=YouTube_Blogger_Automation
SHEET_NAME=Production

# Google Drive 文件夹 ID
DRIVE_FOLDER_ID=你的文件夹ID

# Whisper 模型配置 (tiny, base, small, medium)
WHISPER_MODEL_SIZE=base
```

### 4. 运行
```bash
# 启用自动化流水线 (会自动读取 .env 配置)
python drive_pipeline.py
```

## 📂 文件说明

-   `drive_pipeline.py`: **推荐使用。** 完整的自动化脚本（含 AI 转录 + Google Drive 上传）。
-   `gsheet_sync.py`: 简易同步脚本（仅尝试通过 API 获取字幕，不支持 AI 转录）。
-   `main.py`: 命令行单任务抓取工具。
-   `temp_audio/`: 运行过程中产生的临时音频存放处。

## ⚠️ 注意事项

-   **VPS 内存**：`base` 模型建议至少 1GB RAM。若内存不足，请将 `WHISPER_MODEL_SIZE` 修改为 `tiny`。
-   **静默运行**：建议在 VPS 上使用 `nohup` 或 `screen` 运行，防止 SSH 断开。
    ```bash
    nohup python3 drive_pipeline.py &
    ```

## 📜 开源协议
MIT
