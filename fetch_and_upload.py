import os
import time
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import yt_dlp
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()

# --- 配置加载 ---
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'YouTube_Blogger_Automation')
SHEET_NAME = os.getenv('SHEET_NAME', 'Production')
DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID', '')  # 第二阶段：Drive 文件夹 ID
RCLONE_MOUNT_PATH = os.getenv('RCLONE_MOUNT_PATH')
RATE_LIMIT = os.getenv('DOWNLOAD_RATE_LIMIT', '5M')
FETCH_LIMIT = int(os.getenv('FETCH_LIMIT', 10))
MIN_DELAY = int(os.getenv('MIN_DELAY', 30))
MAX_DELAY = int(os.getenv('MAX_DELAY', 120))
LOCAL_TEMP_DIR = os.getenv('LOCAL_TEMP_DIR', 'temp_audio')

if not os.path.exists(LOCAL_TEMP_DIR):
    os.makedirs(LOCAL_TEMP_DIR)

# --- 授权初始化 ---
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)

# Sheets 客户端
gc = gspread.authorize(creds)
spreadsheet = gc.open(SPREADSHEET_NAME)
production_sheet = spreadsheet.worksheet(SHEET_NAME)

# Drive 客户端 (用于第二阶段上传)
drive_service = build('drive', 'v3', credentials=creds)

def upload_to_drive(local_path, filename):
    """将文件上传到 Google Drive 文件夹"""
    print(f"📡 正在搬运至云端: {filename}...")
    file_metadata = {'name': filename}
    if DRIVE_FOLDER_ID:
        file_metadata['parents'] = [DRIVE_FOLDER_ID]
    
    media = MediaFileUpload(local_path, mimetype='audio/mpeg', resumable=True)
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    return file.get('id')

def fetch_and_upload_v2():
    """LA 节点逻辑：下载 + 上传云端"""
    print("🚀 LA 抓取节点启动，正在扫描任务...")
    
    records = production_sheet.get_all_values()
    processed_count = 0
    
    for i, row in enumerate(records[1:], start=2):
        if processed_count >= FETCH_LIMIT:
            break
            
        video_url = row[0]
        video_id = row[1]
        status = row[2] if len(row) > 2 else ""
        
        # 仅处理需要抓取的行
        if video_id and (status == "等待下载" or status == "" or status == "等待处理"):
            if "音频已就绪" in status:
                continue

            print(f"\n--- 正在处理: {video_id} ---")
            
            # 使用本地临时目录中转
            local_path = os.path.join(LOCAL_TEMP_DIR, f"{video_id}.mp3")
            
            # yt-dlp 配置 (限速控制)
            ydl_opts = {
                'format': 'm4a/bestaudio/best',
                'outtmpl': os.path.join(LOCAL_TEMP_DIR, f'{video_id}.%(ext)s'),
                'ratelimit': 5242880, # 5M
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'quiet': True,
            }

            try:
                # 随机延迟防风控
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                print(f"⏳ 安全等待 {delay:.1f} 秒...")
                time.sleep(delay)
                
                print(f"📥 正在下载 (限速 {RATE_LIMIT})...")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                
                # 上传逻辑
                if DRIVE_FOLDER_ID:
                    upload_to_drive(local_path, f"{video_id}.mp3")
                    # 上传成功后清理本地空间
                    os.remove(local_path)
                    print(f"🧹 本地缓存已清理")
                elif RCLONE_MOUNT_PATH:
                    # 如果使用 Rclone 挂载模式
                    dest_path = os.path.join(RCLONE_MOUNT_PATH, f"{video_id}.mp3")
                    os.rename(local_path, dest_path)
                    print(f"📦 已移动至 Rclone 挂载点")

                # 更新 Sheets
                production_sheet.update_cell(i, 3, "音频已就绪")
                print(f"✅ 处理完成 (行 {i})")
                processed_count += 1
                
            except Exception as e:
                print(f"❌ 失败 {video_id}: {str(e)}")
                production_sheet.update_cell(i, 3, "抓取失败")

if __name__ == "__main__":
    while True:
        try:
            fetch_and_upload_v2()
            print("\n进入休眠，等待下一轮 (10分钟)...")
            time.sleep(600)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"错误: {e}")
            time.sleep(300)
