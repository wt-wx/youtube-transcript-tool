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
    active_task_count = 0 # 记录当前表格中还有多少个待处理的活跃任务
    blank_rows_pool = []  # 记录可以作为“燃料”的空白状态行
    
    # 🔍 第一遍扫描：全局活性探测与空盘统计
    for i, row in enumerate(records[1:], start=2):
        video_id = row[1] if len(row) > 1 else ""
        status = row[2] if len(row) > 2 else ""
        transcript_cell = row[4] if len(row) > 4 else ""

        if not video_id:
            continue
            
        # 探测当前活跃任务数量（需要音频或还需要视频的）
        need_audio = (status == "等待处理" and not transcript_cell)
        need_video = Config.COLLECT_FULL_VIDEO and ("视频" not in status and "失败" not in status)
        
        if need_audio or need_video:
            active_task_count += 1
            
        # 收集可以被激活的燃料（状态完全空白的）
        if status.strip() == "":
            blank_rows_pool.append(i)

    print(f"📊 当前池状态: 活跃任务={active_task_count} 条, 待激活燃料池={len(blank_rows_pool)} 条")
    
    # 🧠 自动续杯逻辑 (Auto-Fill)：如果活跃任务彻底耗尽，且燃料池还有货，自动点燃下 300 条
    if active_task_count == 0 and len(blank_rows_pool) > 0:
        activate_count = min(300, len(blank_rows_pool))
        print(f"🔥 触发『自动续杯』: 正在将下 {activate_count} 条空白任务标记为 '等待处理'...")
        
        batch_updates = []
        for row_idx in blank_rows_pool[:activate_count]:
            batch_updates.append({
                'range': f'C{row_idx}',
                'values': [['等待处理']]
            })
            
        try:
            production_sheet.batch_update(batch_updates)
            print("✅ 自动续杯成功！本轮立刻开始处理新燃料...")
            # 重新获取最新的记录，以便下面的抓取逻辑可以直接吃进这批新的
            records = production_sheet.get_all_values()
        except Exception as e:
            print(f"⚠️ 自动续杯失败: {e}")
            
    # 🏎️ 第二遍扫描：真正的抓取执行阶段
    for i, row in enumerate(records[1:], start=2):
        if processed_count >= Config.FETCH_LIMIT:
            break
            
        video_url = row[0]
        video_id = row[1] if len(row) > 1 else ""
        status = row[2] if len(row) > 2 else ""
        transcript_cell = row[4] if len(row) > 4 else ""
        
        # 🛡️ 多阶状态核查：音频与视频状态解耦
        if not video_id:
            continue

        # 判断是否需要下载音频
        need_audio = (status == "等待处理" and not transcript_cell)
        
        # 判断是否需要下载视频 (如果全视频开启，且当前状态里没标记含视频，也没标记失败)
        need_video = Config.COLLECT_FULL_VIDEO and ("视频" not in status and "失败" not in status)

        if not need_audio and not need_video:
            continue

        try:
            # 随机延迟防风控
            delay = random.uniform(Config.MIN_DELAY, Config.MAX_DELAY)
            print(f"⏳ 命中任务 (行 {i}): 音频需要={need_audio}, 视频需要={need_video} -> 随机等待 {delay:.1f} 秒...")
            time.sleep(delay)
            
            # --- 1. 下载音频 (ASR 必备) ---
            if need_audio:
                audio_path = os.path.join(Config.LOCAL_TEMP_DIR, f"{video_id}.mp3")
                ydl_opts_audio = {
                    'format': 'm4a/bestaudio/best',
                    'outtmpl': os.path.join(Config.LOCAL_TEMP_DIR, f'{video_id}.%(ext)s'),
                    'ratelimit': 5242880, 
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '128'}],
                    'quiet': True,
                }
                
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
            if need_video:
                print(f"🎬 正在采集完整视频...")
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
                    google.upload_to_drive(video_path, f"{video_id}.mp4", folder_id=Config.VIDEO_DRIVE_FOLDER_ID)
                    if os.path.exists(video_path): os.remove(video_path)
                elif Config.RCLONE_MOUNT_PATH:
                    dest_video = os.path.join(Config.RCLONE_MOUNT_PATH, "full_videos", f"{video_id}.mp4")
                    os.makedirs(os.path.dirname(dest_video), exist_ok=True)
                    os.rename(video_path, dest_video)

            # --- 3. 更新 Sheets ---
            # 为了平滑过渡和兼容旧系统：如果没有采集视频，就用 `音频已就绪`
            # 如果采集了视频，我们可以在原来的状态基础上，增加视频标识，例如 `音视频已就绪`
            if need_audio and not need_video:
                new_status = "音频已就绪"
            elif need_video:
                if status == "等待处理" and transcript_cell:
                    new_status = "包含视频等待处理" # 不破坏 AI 接管标志
                elif status == "音频已就绪" or need_audio:
                    new_status = "音视频已就绪"
                else:
                    new_status = f"{status}(视频已就绪)" # 通用追加
            else:
                new_status = status
            
            if new_status != status:
                production_sheet.update_cell(i, 3, new_status)
                
            print(f"✅ 处理完成 (行 {i}) -> 更新为: {new_status}")
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
