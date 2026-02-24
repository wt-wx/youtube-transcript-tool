import os
import time
import random
import yt_dlp
from src.core.config import Config
from src.core.google_api import GoogleClient

def fetch_and_upload():
    """LA 节点逻辑：下载 + 上传云端"""
    Config.ensure_dirs()
    google = GoogleClient()
    production_sheet = google.get_production_sheet()
    
    print("🚀 LA 抓取节点启动 (已模块化)，正在扫描任务...")
    
    records = production_sheet.get_all_values()
    processed_count = 0
    
    for i, row in enumerate(records[1:], start=2):
        if processed_count >= Config.FETCH_LIMIT:
            break
            
        video_url = row[0]
        video_id = row[1]
        status = row[2] if len(row) > 2 else ""
        transcript_cell = row[4] if len(row) > 4 else ""
        
        # 🛡️ 核心修复：仅处理“等待处理”且“字幕为空”的行
        # 如果字幕不为空，说明 HK 节点已处理完，当前状态是为了触发 AI 发布，LA 节点必须跳过。
        if video_id and status == "等待处理":
            if transcript_cell:
                # 这是一个已转录完成、等待 AI 处理的任务，直接跳过
                continue

            print(f"\n--- 正在处理: {video_id} ---")
            local_path = os.path.join(Config.LOCAL_TEMP_DIR, f"{video_id}.mp3")
            
            # yt-dlp 配置 (限速控制)
            ydl_opts = {
                'format': 'm4a/bestaudio/best',
                'outtmpl': os.path.join(Config.LOCAL_TEMP_DIR, f'{video_id}.%(ext)s'),
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
                delay = random.uniform(Config.MIN_DELAY, Config.MAX_DELAY)
                print(f"⏳ 安全等待 {delay:.1f} 秒...")
                time.sleep(delay)
                
                print(f"📥 正在下载 (限速 {Config.RATE_LIMIT})...")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                
                # 上传逻辑
                if Config.DRIVE_FOLDER_ID:
                    google.upload_to_drive(local_path, f"{video_id}.mp3")
                    if os.path.exists(local_path):
                        os.remove(local_path)
                    print(f"🧹 本地缓存已清理")
                elif Config.RCLONE_MOUNT_PATH:
                    dest_path = os.path.join(Config.RCLONE_MOUNT_PATH, f"{video_id}.mp3")
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
            fetch_and_upload()
            print(f"\n进入休眠，等待下一轮 ({10} 分钟)...")
            time.sleep(600)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"运行时错误: {e}")
            time.sleep(300)
