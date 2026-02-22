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

## 🏗️ 工业化部署与运维 (Ops Hub)

本项目已实现高度自动化。建议在 **HP-G3 堡垒机** 上统一管理所有节点的部署与数据桥挂载。

### 1. 自动化运维任务清单

在 Ops Hub 的 `ops/` 目录下（或根目录），使用 `fab` 命令：

| 任务 | 命令 | 说明 |
| :--- | :--- | :--- |
| **安装 Rclone** | `fab install-rclone` | 在 HK 节点全自动下载并安装指定版本的 Rclone |
| **挂载云盘** | `fab mount-drive` | 一键建立从 Google Drive 到 `/opt/google_drive` 的 FUSE 通道 |
| **全量部署** | `fab deploy` | 同步最新代码、分发配置、安装 Venv、重启服务进程 |

### 2. 核心部署流程 (一键投产)

1. **配置鉴权**：在本地运行 `python auth_setup.py` 获取 `token.json`（**务必勾选 Drive 和 Sheets 两个权限**）。
2. **环境对齐**：在 HK 节点运行 `sudo apt install fuse3 -y`（Debian 12/13 必备）。
3. **一键挂载**：
   ```bash
   # 在 HP-G3 的 ops 目录下
   fab mount-drive --group external_nodes --role hk
   ```
4. **全量启动**：
   ```bash
   fab deploy --group external_nodes --role hk
   ```

---

### 3. 工业级运维排障矩阵 (Ops Hub Handbook)

| 症状 | 根因 | 修复动作 |
| :--- | :--- | :--- |
| **Blogger 没出文章** | 阶段三 Apps Script 未触发 | 进入 Sheets -> 扩展程序 -> Apps Script 手动点运行 |
| **"missing scopes" 报错** | `token.json` 权限不足 | **删掉本地 token.json**，重新运行 `auth_setup.py` 并勾选 Sheets 复选框 |
| **"Daemon timed out"** | 缺少 FUSE3 环境 | 在 HK 节点执行 `sudo apt install fuse3 -y` |
| **CPU 100% 且系统卡死** | 模型过重 & Swap 抖动 | 在 `.env.hk` 中将 `WHISPER_MODEL_SIZE` 降级为 `small` 且开启 `int8` |
| **LA 节点不抓取** | C 列 (Status) 为空 | 在 Sheets 中手动或批量将 C 列改为 `等待处理` |

---

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