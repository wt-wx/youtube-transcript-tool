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

            # --- 1. 下载音频 (ASR 必备) ---
            audio_path = os.path.join(Config.LOCAL_TEMP_DIR, f"{video_id}.mp3")
            ydl_opts_audio = {
                'format': 'm4a/bestaudio/best',
                'outtmpl': os.path.join(Config.LOCAL_TEMP_DIR, f'{video_id}.%(ext)s'),
                'ratelimit': 5242880, 
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '128'}],
                'quiet': True,
            }

            try:
                # 随机延迟防风控
                delay = random.uniform(Config.MIN_DELAY, Config.MAX_DELAY)
                print(f"⏳ 安全等待 {delay:.1f} 秒...")
                time.sleep(delay)
                
                print(f"📥 正在下载音频 (限速 {Config.RATE_LIMIT})...")
                with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
                    ydl.download([video_url])
                
                # 上传音频
                if Config.DRIVE_FOLDER_ID:
                    google.upload_to_drive(audio_path, f"{video_id}.mp3")
                    if os.path.exists(audio_path): os.remove(audio_path)
                elif Config.RCLONE_MOUNT_PATH:
                    dest_audio = os.path.join(Config.RCLONE_MOUNT_PATH, f"{video_id}.mp3")
                    os.rename(audio_path, dest_audio)

                # --- 2. 下载视频 (可选备份) ---
                if Config.COLLECT_FULL_VIDEO:
                    print(f"🎬 [PRD 扩展] 正在采集完整视频...")
                    video_path = os.path.join(Config.LOCAL_TEMP_DIR, f"{video_id}.mp4")
                    ydl_opts_video = {
                        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                        'outtmpl': video_path,
                        'ratelimit': 5242880,
                        'quiet': True,
                    }
                    with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
                        ydl.download([video_url])
                    
                    # 上传视频到专用目录
                    if Config.VIDEO_DRIVE_FOLDER_ID:
                        google.upload_to_drive(video_path, f"{video_id}.mp4", folder_id=CONFIG.VIDEO_DRIVE_FOLDER_ID)
                        if os.path.exists(video_path): os.remove(video_path)
                    elif Config.RCLONE_MOUNT_PATH:
                        dest_video = os.path.join(Config.RCLONE_MOUNT_PATH, "full_videos", f"{video_id}.mp4")
                        os.makedirs(os.path.dirname(dest_video), exist_ok=True)
                        os.rename(video_path, dest_video)

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
