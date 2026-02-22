# Rclone Mount Setup on Debian 12/13
Created: 2026-02-22

## 核心发现
在 Debian 12 (Bookworm) 和 Debian 13 (Trixie) 中，默认的 FUSE 系统已迁移至 **FUSE3**。Rclone 的挂载逻辑默认会调用 `fusermount3`。

## 关键症状
- 错误信息：`failed to mount FUSE fs: fusermount: exec: "fusermount3": executable file not found`
- 挂载报错：`Daemon timed out` (Error code 1)

## 修复流程
1. **安装 FUSE3**：`sudo apt update && sudo apt install fuse3 -y`
2. **启用合规挂载权限**：
   ```bash
   echo "user_allow_other" | sudo tee /etc/fuse.conf
   ```
3. **运维指令 (Fabric)**：确保 `fabfile.py` 中的挂载任务使用 `--daemon` 以便持久化。

## 最佳实践
在自动化运维脚本中，应包含对 `fuse3` 的前置检查或自动安装逻辑，以提高部署可靠性。
