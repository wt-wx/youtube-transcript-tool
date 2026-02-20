# YouTube Content Automation Factory 🚀

一个工业级的 YouTube 内容自动化生产线。它采用分布式架构，能够高效地处理大规模频道存量视频的字幕抓取、语音识别（ASR）以及多平台内容转化。

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

## 🛠️ 环境要求与安装

### 1. 系统依赖 (LA/HK 两个节点均需安装)
- **Python 3.10+**
- **FFmpeg**: 核心组件。LA 节点用于提取音轨，HK 节点用于语音解码。
- **Python Pip & Venv**: 用于管理依赖和虚拟环境。

```bash
# Ubuntu/Debian 环境初始化
sudo apt update
sudo apt install ffmpeg python3-pip python3-venv -y
```

### 2. 创建并激活虚拟环境 (推荐)
为了保持服务器全局环境纯净，建议在项目根目录下使用虚拟环境：

```bash
# 1. 创建虚拟环境 (名为 venv)
python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate

# 激活后，你的命令行提示符前会出现 (venv) 字样
```

### 3. 安装项目依赖
激活虚拟环境后，根据节点角色安装所需组件：

- **LA 节点 (抓取)**:
  ```bash
  pip install yt-dlp gspread oauth2client google-api-python-client python-dotenv
  ```
- **HK 节点 (转录)**:
  ```bash
  pip install faster-whisper gspread oauth2client python-dotenv
  ```

## 📦 快速开始

### 1. Google 项目与 Drive 配置
1. **获取凭据**：在 Google Cloud 下载服务账号密钥，重命名为 `credentials.json` 放入项目根目录。
2. **开启 API**：确保在 GCP Console 开启了 **Sheets API** 和 **Drive API**。
3. **设置中转文件夹**：
   - 在 Google Drive 创建文件夹（如 `youtube_factory`）。
   - **共享**：将该文件夹共享给服务账号的 Email，权限设为 **“编辑者”**。
   - **获取 ID**：复制文件夹 URL 中的最后一串字符。

### 2. 环境配置 (.env)
在根目录创建 `.env` 文件：
```env
CREDENTIALS_FILE=credentials.json
SPREADSHEET_NAME=YouTube_Blogger_Automation

# 填入你刚才准备的文件夹 ID
DRIVE_FOLDER_ID=你的文件夹ID

# 节点特定配置
FETCH_LIMIT=10
WHISPER_MODEL_SIZE=medium
```

## 🚀 节点部署指南

本项目采用工业级集中化部署方案，通过 `fabric` 结合统一的 `inventory.yaml` 进行自动化运维部署。

### 1. HP-G3 Ops Hub 集中化一键部署 (推荐)

在环境配置中心（如 HP-G3 Bastion Host）执行一键分发与进程拉起：

1. **环境准备 (HP-G3 上仅需执行一次)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install fabric pyyaml
   ```

2. **配置 Inventory 与私钥**
   确保 HP-G3 项目根目录下的 `inventory.yaml` 配置了目标节点组（如 `external_nodes`），以及正确的 `key_filename` 私钥路径映射。私钥由 Ops Hub 集中保管，不在目标机保存密码。

3. **执行自动化部署**
   一键完成：SSH 远控 -> 环境检查 -> Git 最新代码拉取 -> 本地配置 (`.env`, `credentials.json` 从 `conf/` 目录) 下发 -> Python venv 修复与依赖安装 -> Pkill 结束旧进程 -> Nohup 无痕后台拉起新进程。

   ```bash
   # 前提必须进入虚拟环境: source venv/bin/activate
   cd ops/
   
   # 部署 LA (抓取/上传) 节点
   fab deploy --group external_nodes --role la
   
   # 部署 HK (AI/转录) 节点
   fab deploy --group external_nodes --role hk
   ```

### 2. 单机手动基础启动
在对应节点的 VPS 上进入项目目录：
```bash
# LA 抓取节点
python3 fetch_and_upload.py

# HK 转录节点
python3 transcribe_and_fill.py
```

### 2. 后台守护 (防止断开 SSH 后中断)
在服务器上，当你关闭终端窗口时，普通运行的程序会随之停止。为了让脚本 24/7 运行，推荐以下两种方案：

#### 方案 A：使用 `screen` (强烈推荐，方便随时查看日志)
`screen` 就像给服务器开了一个“虚拟桌面”，你退出了 SSH，桌面还在。

1. **安装** (若没有)：`sudo apt install screen`
2. **创建一个新窗口**：
   ```bash
   screen -S youtube_task
   ```
3. **在窗口中启动脚本**：
   ```bash
   python3 fetch_and_upload.py
   ```
4. **退出窗口（保持运行）**：按下键盘 `Ctrl + A`，然后按 `D` (Detach)。现在你可以放心关闭终端了。
5. **下次回来查看进度**：
   ```bash
   screen -r youtube_task
   ```

#### 方案 B：使用 `nohup` (简单、无需安装)
如果你不需要频繁交互，只想让它死跑。

1. **启动并忽略挂断信号**：
   ```bash
   nohup python3 fetch_and_upload.py > task.log 2>&1 &
   ```
   - `> task.log`: 将所有输出记录到这个文件。
   - `2>&1`: 把错误信息也合并到日志。
   - `&`: 让程序直接进入后台。
2. **如何停止它**：
   ```bash
   # 找到进程 ID
   ps -ef | grep fetch_and_upload.py
   # 杀掉它 (PID 是输出中的数字)
   kill PID
   ```

## 📂 项目结构

```text
/
├── fetch_and_upload.py    # LA 节点启动入口
├── transcribe_and_fill.py # HK 节点启动入口
├── diagnostic.py          # 环境诊断工具
├── src/                   # 核心源代码
│   └── core/              # 配置与 API 客户端封装
├── ops/                   # Fabric 自动化运维部署脚本
│   └── fabfile.py         # 核心部署控制逻辑 (依循 server-ops-hub 规范)
├── conf/                  # 本地/堡垒机配置目录 (存放 .env.la, .env.hk 及 json)，部署时向外分发
├── inventory.yaml         # Ops Hub 节点信息资产清单 (主机/端口/用户/密钥)
├── legacy/                # 历史/备选管线脚本 (归档)
├── .env.example           # 环境变量配置模版
└── requirements.txt       # Python 依赖清单
```

## 📜 常用命令

### 1. 环境诊断
在部署前，运行此脚本检查 Google API 权限：
```bash
python3 diagnostic.py
```

### 2. 启动生产线
```bash
# LA 节点
python3 fetch_and_upload.py

# HK 节点
python3 transcribe_and_fill.py
```
MIT License

https://geniux.net