# YouTube Content Factory 部署记忆与排坑指南 (2026-02-20)

本文档记录了基于 HP-G3 的 **Ops Hub 集中化部署 (Fabric Push)** 架构至海外双节点 (LA 节点和 HK 节点) 时的全量踩坑与解决方案，作为未来的部署和排障参考，避免重复踩坑。

## 一、 Ops Hub (HP-G3) 部署架构原则
1. **Push 控制架构**:
   由 HP-G3 作为主控端（Bastion Host），向没有任何 Git 权限和源码权限的目标 VPS (LA / HK) 强行推送代码、配置和执行重启。
2. **私钥权限收敛**:
   HP-G3 统一保管对应的免密私钥 (`.ssh/id_ed25519_1panel` 等) 和项目核弹级配置 `credentials.json`。
3. **不可提交 (Untracked) 清单**:
   运维配置文件 `inventory.yaml` 饱含真实机器 IP 与私钥地址，绝对不可提交至 GitHub，代码库只保留 `inventory.example.yaml` 供参考。新建部署机需手动拷贝建立。

## 二、 核心血泪坑点与终极解法

### 1. `Permission denied` - /opt 系统目录写入权限问题
- **现象**: 尝试部署至 `/opt/youtube-factory` 目录报错无权限建立文件夹或解压文件。
- **原因**: `inventory.yaml` 中的 SSH 用户配置为普通用户 (`geniux`)，无法直接操作系统级 `/opt` 目录。
- **解法**:
  放弃 `sudo` 提权提心吊胆的方案，因为我们习惯全尺寸 root 操作。直接在 `inventory.yaml` 里将所有下属节点的 user 改为 `root`。即：部署动作从头到尾一律作为 root 连入节点全尺寸执行！

### 2. `Authentication failed` - 钥匙与锁不匹配问题
- **现象**: `fab deploy` 命令报 Authentication failed 身份验证失败，但网络畅通且无防火墙阻拦。
- **原因**: `inventory.yaml` 里配错了私钥路径。HP-G3 （工作兵）包里没有带对应 LA 节点的身份私钥文件，它拿着 `1panel` 的私钥去开只认 `antigravity-ops` 公钥的 LA 大门。
- **解法**: 
  核查目标节点（例如 LA 的 `bwg`）的 `/root/.ssh/authorized_keys` 中实际记录的公钥结尾身份。
  确保 HP-G3 堡垒机里 `/root/.ssh/` 存放有相对应的那把私钥文件，随后精准地在 `inventory.yaml` 里将该节点的 `key_filename` 指向这把正确的私钥。

### 3. 被系统封印的 Root - 修改 sshd_config
- **现象**: 即使全套私钥均无误，以 root 连接照旧报 `Authentication failed` 拒绝登录。
- **原因**: 诸多提供商 (Debian 默认等) 在开机初始化时，安全防御机制关闭了远控机器直接通过 `root` 账户登录的权限。
- **解法**:
  登入目标节点开启：
  ```bash
  vim /etc/ssh/sshd_config
  # 改为
  PermitRootLogin prohibit-password   # (只允密钥免密)，或粗暴打 yes
  # 退出并重启生效，无需 sudo（既然已是 root）：
  systemctl restart sshd
  ```

### 4. Venv 虚拟环境构建失败 (ensurepip is not available)
- **现象**: `python3 -m venv venv` 失败，后续的 `pip install` 长出 No such file or directory：`/venv/bin/pip` 找不到。
- **原因**: Debian/Ubuntu 虽然默认带有非常素的 Python 版本环境，但不包含构建虚拟环境赖以前置的底层环境库 (`python3.11-venv` 或对应版本)，这就导致新建出的虚机其实是个毫无 pip 工兵的残废"烂尾楼"。
- **解法 (必须在目标机修补)**:
  1. 切入目标机清理烂尾现场：`rm -rf /opt/youtube-factory/venv`
  2. 安装底层包补足组件：`apt update && apt install python3-pip python3.11-venv -y` (记得捎上 ffmpeg)
  3. 然后 HP-G3 重新发车 `fab deploy` 将顺滑无比。

### 5. SSH 指令阻塞 (卡住无法退出 TTY)
- **现象**: 输出 `🔄 Restarting service...` 之后，部署一直停滞挂起，HP-G3 假死无法退回命令提示符。
- **原因**: fabric 调用 `nohup` 仍会导致僵尸拦截。只要后台程序的标准输入输出或任何文件描述符还捏在 SSH Session 的手里，即便扔进后台，Fabric 也认为通道没结束拒绝脱离。
- **终极解法 (在 fabfile.py 执行段):**
  增加 `</dev/null` 切断 TTY 监听流，增加 `disown` 分剥操作系统从属；并且加上 Invoke 推荐的参数抛弃响应要求。
  ```python
  cmd = f"nohup {{python_bin}} {{script}} > task.log 2>&1 </dev/null & disown"
  conn.run(cmd, hide=True, asynchronous=True)
  ```
  这一句加上后，HP-G3 在重启动作发出的即刻，立刻优雅退出 SSH 控制台回到纯净的本地命令行！
