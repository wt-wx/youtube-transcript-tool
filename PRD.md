**项目需求规格书（Requirement Specification）**。

---

## 项目：多频道 YouTube-to-Blogger AI 内容自动化工厂

### 1. 架构逻辑：分布式生产线

* **节点 A (LA VPS - 采集与搬运)**：
* **核心功能**：监控频道、采集链接、调用 `yt-dlp` 提取音频、上传至 Google Drive。
* **流量控制**：限制下载速率，模拟人类访问，规避 YouTube IP 风控。

* **节点 B (HK VPS - 核心工坊)**：
* **核心功能**：从 Google Drive 下载音频、运行 **Faster-Whisper** 生成字幕、回填 Google Sheets。

* **节点 C (Google Workspace - 调度中心)**：
* **Sheets**：作为全局任务队列（Task Queue）。
* **Drive**：作为音视频文件的中转仓库与持久化存储。
* **Apps Script**：负责最后的 Gemini 生成与多博客分发。

---

### 2. 详细功能模块需求

#### **模块一：LA 节点 - “隐匿搬运工”**

1. **限速下载**：配置 `yt-dlp` 参数 `--limit-rate 5M`（根据带宽调整），确保流量平稳。
2. **多格式备份**：
* 视频：最高分辨率 MP4 存入 Google Drive 的 `Video_Backup` 文件夹。
* 音频：提取 128kbps M4A 存入 `Audio_Queue` 文件夹。


3. **多频道兼容**：读取 `Config` 表中的频道列表，自动在 Drive 创建对应的子文件夹。

#### **模块二：HK 节点 - “语言翻译官”**

1. **断点扫描**：每 5 分钟扫描 Google Sheets，寻找“待转录”状态的行。
2. **本地推理**：加载 `large-v3` 或 `medium` 模型。中文视频强制使用 `initial_prompt` 以减少繁简错误。
3. **负载管理**：HK VPS 仅在检测到新音频时启动推理，避免 CPU 长期空转。

#### **模块三：多频道扩展引擎 (Multi-Channel Engine)**

1. **统一数据库**：在 `Production` 表增加 `Channel_Key` 列。
2. **动态分发**：Gemini 生成时，根据 `Channel_Key` 自动匹配对应的 **Blogger ID** 和 **Prompt Style**。

---

### 3. Antigravity 部署指令清单

请将以下逻辑输入到你的管理工具中执行：

#### **Step 1: 环境初始化 (双机同步)**

* **LA & HK**：安装 `Python 3.10+`, `ffmpeg`, `rclone`。
* **配置 rclone**：在两台 VPS 上配置相同的 Google Drive 挂载点，确保文件同步无缝。

#### **Step 2: 核心代码部署**

* **LA 运行 `fetch_and_upload.py**`：
* 逻辑：监控 Sheets -> `yt-dlp` 限速下载音频 -> 上传 Drive -> 更新 Sheets 状态为“音频已就绪”。


* **HK 运行 `transcribe_and_fill.py**`：
* 逻辑：监控 Sheets (状态=音频已就绪) -> 从 Drive 读取音频 -> Faster-Whisper 转录 -> 回填 E 列 -> 更新状态为“等待处理”。

#### **Step 3: Apps Script 触发器**

* 设置每小时运行一次 `batchProcessVideos`，完成最后的 AI 撰写与发布。

---

### 4. 关键风险规避设置

* **YouTube 风控**：在 LA VPS 脚本中引入随机等待时间 `random.uniform(30, 120)`，且每次采集不超过 50 条。
* **硬盘保护**：文件上传至 Google Drive 成功后，必须执行 `os.remove()` 物理删除 VPS 本地缓存。

---