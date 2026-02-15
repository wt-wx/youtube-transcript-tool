# YouTube Transcript Automation Factory 🚀

这是一个工业级的 YouTube 内容自动化流水线。它采用分布式架构，能够高效地处理大规模视频字幕抓取、语音识别（ASR）以及数据回填。

## 🏗️ 分布式架构设计

为了优化效率并降低风控风险，项目支持分布式部署模式：

- **LA 节点 (Capture)**: 部署在离 YouTube 服务器近的 VPS（如洛杉矶），负责限速抓取、音频提取并搬运至云端存储（Google Drive/Rclone）。
- **HK 节点 (Intelligence)**: 部署在计算资源充足的 VPS（如香港），负责从云端拉取音频，并运行 `Faster-Whisper` 推理生成高质量字幕。
- **调度中心 (Google Sheets)**: 作为全局任务队列平衡各个节点的生产进度。

## 🌟 核心特性

- **分布式生产线**：支持 LA/HK 双节点模式，自动同步状态。
- **隐匿搬运**：LA 节点支持 `yt-dlp` 限速下载与随机等待，完美规避 YouTube 风控。
- **高精度 AI 转录**：基于 `Faster-Whisper` 的 `large-v3` 或 `medium` 模型，针对中文优化了 `initial_prompt`。
- **云端持久化**：支持通过 Google Drive 或 Rclone 挂载点进行音频中转，无需 VPS 长期占用硬盘。

## 🛠️ 环境要求

- Python 3.10+
- **FFmpeg** (必须安装，用于音频提取)
- Google Cloud 服务账号凭据 (`credentials.json`)
- Rclone (若需要多节点自动同步)

## 📦 快速开始

### 1. 安装依赖

```bash
pip install youtube-transcript-api gspread oauth2client yt-dlp faster-whisper google-api-python-client google-auth-httplib2 google-auth-oauthlib python-dotenv
```

### 2. Google 项目配置

1. 在 Google Cloud Console 下载密钥并命名为 `credentials.json`。
2. 开启 Google Sheets 和 Google Drive API。
3. 将表格共享给服务账号的 Email 地址。

### 3. 环境配置 (.env)

根据节点角色在根目录配置 `.env`：

```env
# 基础配置
CREDENTIALS_FILE=credentials.json
SPREADSHEET_NAME=YouTube_Blogger_Automation

# Rclone 挂载路径 (关键：确保 LA 和 HK 节点指向同一个同步文件夹)
RCLONE_MOUNT_PATH=/mnt/gdrive/youtube_audio

# LA 节点配置
DOWNLOAD_RATE_LIMIT=5M
FETCH_LIMIT=20

# HK 节点配置
WHISPER_MODEL_SIZE=medium
TRANSCRIPTION_LIMIT=10
```

## 🚀 节点部署指南

### LA 抓取节点 (搬运工)
负责监控表格状态，下载音频并存入 Rclone 挂载点。
```bash
python3 fetch_and_upload.py
```

### HK 转录节点 (翻译官)
负责从 Rclone 读取音频，完成语音识别并回填字幕至 Google Sheets。
```bash
python3 transcribe_and_fill.py
```

## 📂 文件说明

- `fetch_and_upload.py`: **LA 节点程序**。限速抓取音频，状态标记为 `音频已就绪`。
- `transcribe_and_fill.py`: **HK 节点程序**。扫描就绪视频，完成 AI 转录，状态标记为 `等待处理`。
- `drive_pipeline.py`: **单机全能版**。适合在单一 VPS 上完成全部流程的小型任务。
- `gsheet_sync.py`: 简易 API 同步脚本。
- `PRD.md`: 项目详细架构需求说明书。

## ⚠️ 注意事项

- **风控规避**：LA 节点的 `fetch_and_upload.py` 内置了 30-120 秒的随机休眠。
- **资源占用**：HK 节点运行 `medium` 模型时建议至少 2GB RAM；运行 `large-v3` 建议 4GB+ RAM。
- **静默后台运行**：
  ```bash
  nohup python3 fetch_and_upload.py &
  ```

## 📜 开源协议
MIT
