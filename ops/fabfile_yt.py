from fabric import task, Connection
import yaml
import os

# --- 全局配置 ---
REMOTE_ROOT = "/opt/youtube-factory"
# 这个是指向你在 HP-G3 的本地目录，确保 conf 文件夹在这里
LOCAL_CONF_DIR = "/opt/antigravity/youtube-factory/conf"
REPO_URL = "https://github.com/wt-wx/youtube-transcript-tool.git"

# --- Inventory 运维逻辑，遵循 server-ops-hub 规范 ---
INVENTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'inventory.yaml')

def load_inventory():
    if not os.path.exists(INVENTORY_FILE):
        return None
    with open(INVENTORY_FILE, 'r') as f:
        return yaml.safe_load(f)

inv = load_inventory()

def get_connection(host_def):
    hostname = host_def.get('host')
    user = host_def.get('user', 'root')
    port = host_def.get('port', 22)
    key_filename = host_def.get('key_filename')
    
    connect_kwargs = {}
    if key_filename:
        # 如果是相对路径 (如 ~/.ssh/...) 则展开用户目录，因为 fabric 在解析 key 时需要绝对路径
        connect_kwargs['key_filename'] = os.path.expanduser(key_filename)

    conn = Connection(
        host=hostname,
        user=user,
        port=port,
        connect_kwargs=connect_kwargs
    )
    return conn

def resolve_targets(group_name):
    if not inv or 'groups' not in inv:
        print(f"[!] Invalid or missing inventory at {INVENTORY_FILE}.")
        return []
    targets = []
    if group_name in inv['groups']:
        group_data = inv['groups'][group_name]
        default_user = group_data.get('user', 'root')
        default_port = group_data.get('port', 22)
        default_key = group_data.get('key_filename')

        for entry in group_data.get('hosts', []):
            host_def = {}
            if isinstance(entry, str):
                host_def['host'] = entry
            elif isinstance(entry, dict):
                host_def = entry.copy()
            
            if 'user' not in host_def: host_def['user'] = default_user
            if 'port' not in host_def: host_def['port'] = default_port
            if 'key_filename' not in host_def and default_key:
                host_def['key_filename'] = default_key
            targets.append(host_def)
    else:
        print(f"[!] Group '{group_name}' not found in inventory.")
    return targets

@task
def deploy(c, group, role):
    """
    全量部署任务，遵循 Ops Hub 规范。
    Usage: fab -f ops/fabfile_yt.py deploy --group=bwg_workers --role=la
    """
    targets = resolve_targets(group)
    if not targets:
        print("❌ No targets found. Aborting.")
        return

    for host_def in targets:
        conn = get_connection(host_def)
        print(f"\n🚀 Starting deployment for role: {role} on {conn.host}:{conn.port} as {conn.user}...")
        
        try:
            with conn:
                # 1. 基础环境
                print("🛠️  Checking remote environment...")
                conn.run(f"mkdir -p {REMOTE_ROOT}")
                
                # 2. 代码同步 (Git)
                print("📦 Syncing code from GitHub...")
                with conn.cd(REMOTE_ROOT):
                    if conn.run("test -d .git", warn=True).failed:
                        conn.run(f"git clone {REPO_URL} .")
                    else:
                        conn.run("git fetch origin main")
                        conn.run("git reset --hard origin/main")

                # 3. 配置分发
                print(f"📁 Uploading configurations for {role}...")
                conn.put(f"{LOCAL_CONF_DIR}/credentials.json", remote=f"{REMOTE_ROOT}/credentials.json")
                
                env_file = f".env.{role}"
                if os.path.exists(f"{LOCAL_CONF_DIR}/{env_file}"):
                    conn.put(f"{LOCAL_CONF_DIR}/{env_file}", remote=f"{REMOTE_ROOT}/.env")
                    print(f"✅ Uploaded {env_file} as .env")
                else:
                    print(f"⚠️  Warning: Local config {LOCAL_CONF_DIR}/{env_file} not found!")

                # 4. 依赖更新 (Venv)
                print("🐍 Updating Python dependencies...")
                venv_dir = f"{REMOTE_ROOT}/venv"
                if conn.run(f"test -d {venv_dir}", warn=True).failed:
                    conn.run(f"python3 -m venv {venv_dir}")
                    conn.run(f"{venv_dir}/bin/pip install --upgrade pip")
                conn.run(f"{venv_dir}/bin/pip install -r {REMOTE_ROOT}/requirements.txt")

                # 5. 服务重启
                restart_service(conn, role)
                print(f"✨ Deployment COMPLETED for {conn.host}!")
                
        except Exception as e:
            print(f"❌ Deployment Failed on {conn.host}: {str(e)}")

def restart_service(conn, role):
    print("🔄 Restarting service...")
    script_map = {
        "la": "fetch_and_upload.py",
        "hk": "transcribe_and_fill.py"
    }
    script = script_map.get(role)
    if not script:
        print(f"❌ Unknown role: {role}")
        return

    python_bin = f"{REMOTE_ROOT}/venv/bin/python"
    conn.run(f"pkill -f {script}", warn=True)
    
    with conn.cd(REMOTE_ROOT):
        cmd = f"nohup {python_bin} {script} > task.log 2>&1 &"
        conn.run(cmd, pty=False)
        
    print(f"✅ Service {script} restarted")
