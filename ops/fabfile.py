from fabric import task, Connection
import yaml
import os

# --- 全局配置 ---
# 远程部署目录 (遵循用户习惯，使用 /opt，并配合 root 操作)
REMOTE_ROOT = "/opt/youtube-factory"
# 这个是指向你在 HP-G3 的本地目录，确保 conf 文件夹在这里
LOCAL_CONF_DIR = "/opt/antigravity/youtube-factory/conf"
REPO_URL = "https://github.com/wt-wx/youtube-transcript-tool.git"

# --- Inventory 运维逻辑，遵循 server-ops-hub 规范 ---
_cur_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.join(os.getcwd(), 'ops')
INVENTORY_FILE = os.path.join(_cur_dir, '..', 'inventory.yaml')

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
    Usage: fab -f ops/fabfile.py deploy --group=bwg_workers --role=la
    """
    targets = resolve_targets(group)
    if not targets:
        print("❌ No targets found. Aborting.")
        return

    for host_def in targets:
        if role == 'la' and 'bwg.la' not in host_def.get('host', ''):
            continue
        if role == 'hk' and 'kty.hk' not in host_def.get('host', ''):
            continue

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
                
                # 优先分发个人 OAuth Token
                if os.path.exists(f"{LOCAL_CONF_DIR}/token.json"):
                    conn.put(f"{LOCAL_CONF_DIR}/token.json", remote=f"{REMOTE_ROOT}/token.json")
                    print("✅ Uploaded User OAuth token.json")
                elif os.path.exists(f"{os.path.dirname(LOCAL_CONF_DIR)}/token.json"): # 兼容如果直接放在根目录的话
                     conn.put(f"{os.path.dirname(LOCAL_CONF_DIR)}/token.json", remote=f"{REMOTE_ROOT}/token.json")
                     print("✅ Uploaded User OAuth token.json")
                
                # 保留 Service Account 凭据作为后备
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
        # 彻底切断标准输入/输出/错误流与 SSH TTY 的关联，防止 Fabric 部署卡死
        cmd = f"nohup {python_bin} {script} > task.log 2>&1 </dev/null & disown"
        # asynchronous=True 让 invoke 不等待进程返回即认为命令完成
        conn.run(cmd, hide=True, asynchronous=True)
        
    print(f"✅ Service {script} restarted")

@task
def mount_drive(c, group, role):
    """
    HK 节点专用：自动化挂载 Google Drive 音频目录。
    Usage: fab mount-drive --group=external_nodes --role=hk
    """
    targets = resolve_targets(group)
    if not targets:
        print("❌ No targets found. Aborting.")
        return

    MOUNT_PATH = "/opt/google_drive"
    REMOTE_NAME = "gdrive"
    REMOTE_FOLDER = "youtube_factory"

    for host_def in targets:
        # 只在 HK 角色节点执行
        if role == 'hk' and 'kty.hk' not in host_def.get('host', ''):
            continue
        
        conn = get_connection(host_def)
        print(f"\n🚀 Checking mount on {conn.host}...")
        
        try:
            with conn:
                print(f"📁 Preparing mount point: {MOUNT_PATH}...")
                conn.sudo(f"mkdir -p {MOUNT_PATH}")
                conn.sudo(f"chown {conn.user}:{conn.user} {MOUNT_PATH}")

                # 检查是否已挂载
                check = conn.run(f"mount | grep {MOUNT_PATH}", warn=True, hide=True)
                if check.ok:
                    print(f"✅ {MOUNT_PATH} is already mounted.")
                    continue

                print("🚀 Mounting Google Drive via Rclone...")
                mount_cmd = (
                    f"rclone mount {REMOTE_NAME}:{REMOTE_FOLDER} {MOUNT_PATH} "
                    f"--daemon --vfs-cache-mode writes --allow-other "
                    f"--buffer-size 32M --dir-cache-time 12h"
                )
                
                result = conn.run(mount_cmd, warn=True)
                if result.ok:
                    print(f"✨ Success! Google Drive mounted at {MOUNT_PATH} on {conn.host}")
                else:
                    print(f"❌ Mount failed on {conn.host}.")
        except Exception as e:
            print(f"❌ Connection error on {host_def.get('host')}: {e}")
