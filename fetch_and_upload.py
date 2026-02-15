import os
import time
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import yt_dlp
from dotenv import load_dotenv

load_dotenv()

# --- 配置加载 ---
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'YouTube_Blogger_Automation')
SHEET_NAME = os.getenv('SHEET_NAME', 'Production')
RCLONE_MOUNT_PATH = os.getenv('RCLONE_MOUNT_PATH')
RATE_LIMIT = os.getenv('DOWNLOAD_RATE_LIMIT', '5M')
FETCH_LIMIT = int(os.getenv('FETCH_LIMIT', 10))
MIN_DELAY = int(os.getenv('MIN_DELAY', 30))
MAX_DELAY = int(os.getenv('MAX_DELAY', 120))

# --- 初始化 ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
gc = gspread.authorize(creds)
spreadsheet = gc.open(SPREADSHEET_NAME)
production_sheet = spreadsheet.worksheet(SHEET_NAME)

def fetch_and_upload():
    """LA 节点核心逻辑：搬运工"""
    print("🚀 LA 抓取节点启动，正在扫描任务...")
    
    # 重新获取数据以保证状态最新
    records = production_sheet.get_all_values()
    processed_count = 0
    
    for i, row in enumerate(records[1:], start=2):
        if processed_count >= FETCH_LIMIT:
            break
            
        video_url = row[0]
        video_id = row[1]
        status = row[2] if len(row) > 2 else ""
        
        # 仅处理状态为【等待下载】或为空且 ID 存在的行
        if video_id and (status == "等待下载" or status == "" or status == "等待处理"):
            # 这里的状态逻辑：为了配合 PRD，我们将初始状态视为“等待下载”
            # 如果目前是“等待处理”，且没有音频，我们也介入
            
            # 检查是否已经标记为音频就绪
            if "音频已就绪" in status:
                continue

            print(f"\n--- 发现任务: {video_id} ---")
            
            # 下载路径：优先使用 Rclone 挂载路径
            output_dir = RCLONE_MOUNT_PATH if RCLONE_MOUNT_PATH else "downloads"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            output_path = os.path.join(output_dir, f"{video_id}.mp3")
            
            # yt-dlp 配置（含限速）
            ydl_opts = {
                'format': 'm4a/bestaudio/best',
                'outtmpl': os.path.join(output_dir, f'{video_id}.%(ext)s'),
                'ratelimit': 5242880, # 5M (单位字节)
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
                'quiet': False,
                'no_warnings': False,
            }

            try:
                # 随机延迟防风控
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                print(f"安全等待 {delay:.1f} 秒...")
                time.sleep(delay)
                
                print(f"正在从 YouTube 下载音频 (限速 {RATE_LIMIT})...")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                
                # 更新状态
                production_sheet.update_cell(i, 3, "音频已就绪")
                print(f"✅ 音频已就绪，已更新表格 (行 {i})")
                processed_count += 1
                
            except Exception as e:
                print(f"❌ 下载失败 {video_id}: {str(e)}")
                production_sheet.update_cell(i, 3, "下载失败")

    print(f"\n任务处理完毕。本次共下载 {processed_count} 条音频。")

if __name__ == "__main__":
    while True:
        try:
            fetch_and_upload()
            print("\n进入休眠，等待下一轮扫描 (10分钟)...")
            time.sleep(600)
        except KeyboardInterrupt:
            print("\n程序由用户停止。")
            break
        except Exception as e:
            print(f"\n运行时发生未知错误: {e}，5分钟后重试...")
            time.sleep(300)
