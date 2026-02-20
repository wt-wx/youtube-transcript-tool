from fabric import task
import os

# --- 全局配置 ---
# 远程部署目录
REMOTE_ROOT = "/opt/youtube-factory"
# 本地配置源 (HP-G3 上的路径)
LOCAL_CONF_DIR = "/opt/antigravity/ops/projects/youtube-factory/conf"
# Git 仓库
REPO_URL = "https://github.com/wt-wx/youtube-transcript-tool.git"

@task
def deploy(c, role):
    """
    全量部署任务：代码同步 -> 配置分发 -> 依赖更新 -> 服务重启
    Usage: fab -H user@ip:port deploy --role=la (or hk)
    Example: fab -H root@1.2.3.4:2222 deploy --role=la
    """
    print(f"🚀 Starting deployment for role: {role} on {c.host}:{c.port or 22}...")

    # 1. 基础环境检查
    print("🛠️  Checking remote environment...")
    c.run(f"mkdir -p {REMOTE_ROOT}")
    
    # 2. 代码同步 (Git)
    print("📦 Syncing code from GitHub...")
    with c.cd(REMOTE_ROOT):
        # 如果目录为空则 clone，否则 pull
        if c.run("test -d .git", warn=True).failed:
            c.run(f"git clone {REPO_URL} .")
        else:
            c.run("git fetch origin main")
            c.run("git reset --hard origin/main") # 强制覆盖本地修改，保持与远程一致

    # 3. 配置分发 (核心步骤：上传 .env 和 credentials)
    print(f"uploading configurations for {role}...")
    # 上传凭据
    c.put(f"{LOCAL_CONF_DIR}/credentials.json", remote=f"{REMOTE_ROOT}/credentials.json")
    
    # 上传对应的 .env
    env_file = f".env.{role}"
    if os.path.exists(f"{LOCAL_CONF_DIR}/{env_file}"):
        c.put(f"{LOCAL_CONF_DIR}/{env_file}", remote=f"{REMOTE_ROOT}/.env")
        print(f"✅ Uploaded {env_file} as .env")
    else:
        print(f"⚠️  Warning: Local config {env_file} not found!")

    # 4. 依赖更新 (Venv)
    print("🐍 Updating Python dependencies...")
    venv_dir = f"{REMOTE_ROOT}/venv"
    # 创建 venv
    if c.run(f"test -d {venv_dir}", warn=True).failed:
        c.run(f"python3 -m venv {venv_dir}")
        c.run(f"{venv_dir}/bin/pip install --upgrade pip")
    
    # 安装依赖
    c.run(f"{venv_dir}/bin/pip install -r {REMOTE_ROOT}/requirements.txt")

    # 5. 服务重启
    restart_service(c, role)

    print(f"✨ Deployment COMPLETED for {c.host}!")

def restart_service(c, role):
    """
    重启服务逻辑
    """
    print("🔄 Restarting service...")
    
    # 确定脚本名称
    script_map = {
        "la": "fetch_and_upload.py",
        "hk": "transcribe_and_fill.py"
    }
    script = script_map.get(role)
    if not script:
        print(f"❌ Unknown role: {role}")
        return

    python_bin = f"{REMOTE_ROOT}/venv/bin/python"
    
    # 杀掉旧进程 (暴力 kill)
    c.run(f"pkill -f {script}", warn=True)
    
    # 后台启动 (nohup)
    with c.cd(REMOTE_ROOT):
        # 使用 nohup 启动，日志写入 task.log
        cmd = f"nohup {python_bin} {script} > task.log 2>&1 &"
        c.run(cmd, pty=False)
        
    print(f"✅ Service {script} restarted (PID check required)")
