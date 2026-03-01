# YouTube Content Automation Factory 🚀

一个工业级的 YouTube 内容自动化生产线。它采用分布式架构，能够高效地处理大规模频道存量视频的字幕抓取、语音识别（ASR）以及多平台内容转化。

## 🏗️ 分布式架构设计

为了优化效率并降低风控风险，项目支持分布式部署模式：

- **LA 节点 (Capture)**: 负责 `yt-dlp` 限速抓取音频，通过 Rclone 搬运至 Google Drive。
- **HK 节点 (ASR)**: 负责推理。采用 `Faster-Whisper` + 内存防崩溃优化（单次加载模式），适配 4G 内存 VPS。
- **调度中心 (Google Sheets)**: 结合 DeepSeek V3 / Gemini 2.0 实现 AI 改写、自动拟题并发布至双 Blogger 站点。

## 🌟 核心特性

- **LLM 路由军团**：集成 DeepSeek, Qwen (Mulerouter), GLM, Kimi, 豆包。支持敏感词拦截自动切流，实现 100% 发布自愈。
- **多厂弹性路由 3.3**：DeepSeek, Qwen 3.5 Plus, GLM-4.7 全量接入，集成内容拦截自动切流与中转站（New-API/LiteLLM）支持。
- **视觉工厂 V2**：智谱 GLM-Image 驱动，自动化封面生成、GD 归档及外链注入。
- **Headless CMS 双轨分发**：彻底移除 WP，实现 Blogger + Contentful/Sanity/Prismic 的全量并发推送能力。
- **方案 A 独立供稿**：三渠道（个人博主、复刻博主、科技新闻）分别调用独立 Prompt，由 LLM 驱动完全差异化的内容输出。
- **全量视频采集 (LA Node)**：支持 MP4 原片与 ASR 音频的双轨采集存证。完整 MP4 视频并归档至云端备份目录。
- **内存防崩溃**：HK 节点通过 10GB Swap + 代码级模型持久化加载，彻底解决 ASR 推理时的 OOM 崩溃。
- **ASR 自愈机制**：HK 节点具备“僵尸行修复”功能，能自动识别并翻转由于网络波动导致的状态卡死任务，确保发布序列完整。
- **Blogger 全自动拟题**：Apps Script 自动实现“AI 拟题 + 正文 HTML 转换”，生成的博文具备标题感且排版整齐。
- **工业级风控**：LA 节点具备随机休眠机制，避免 YouTube 账号及 IP 被封。

## 🏗️ 工业化部署与运维 (Ops Hub)

本项目符合 **Antigravity 3.0 运维规范**。建议在堡垒机使用 `fab` 统一分发负载。

### 1. 自动化运维任务清单

| 任务 | 命令 | 说明 |
| :--- | :--- | :--- |
| **全量部署** | `fab deploy` | 同步最新单次加载代码、配置 Venv、重启 HK/LA 进程 |
| **扩容 Swap** | (手动) | 执行 `sudo swapon /swapfile` 将 Swap 提升至 8GB+ |

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

### 3. 单机手动基础启动
在对应节点的 VPS 上进入项目目录：
```bash
# LA 抓取节点
python3 fetch_and_upload.py

# HK 转录节点
python3 transcribe_and_fill.py
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
### 4. 稳健分发方案 (Anti-Ban Drip-Feed)
为了彻底规避 Google 风控判定为垃圾内容，系统已进入 **“极度保守”** 生产模式：

- **发布频率**：每天 **5 篇**（约每 3 小时 1 篇）。
- **执行逻辑**：脚本每次仅处理 1 条记录，完成后立即退出。
- **配置步骤**：
  1. 打开 Apps Script，确保已部署 `dripFeedWorkflow`。
  2. 点击编辑器左侧闹钟图标（触发器），添加函数 `dripFeedWorkflow`。
  3. 设置为 **时间驱动** -> **小时定时器** -> **每 2 小时** 或 **每 4 小时** 执行一次。
  4. 检查日志，确保脚本在非发布时间（22:00 - 08:00）自动静默。

## 🚀 下一步：自动化播客工厂 (Podcast Factory)

目前项目已成功覆盖“视频 -> 图文”链路。接下来的重点是利用图文基座，拓展音频资产矩阵：

- **NotebookLM 自动化**：通过 Browser Agent 实现 NotebookLM "Audio Overview" 的自动生成，打造高保真 AI 对谈播客。
- **纯 API 播客管线**：DeepSeek 角色化剧本 + 品牌级 TTS (OpenAI TTS/Fish Speech)，实现播客全流程无人值守发布。
- **RSS 自动分发**：构建专有的音频 RSS 服务，一键分发至 Apple Podcast / Spotify。

---
MIT License

https://geniux.net