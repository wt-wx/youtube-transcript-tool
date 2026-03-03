import os
import time
from faster_whisper import WhisperModel
from src.core.config import Config
from src.core.google_api import GoogleClient

def run_worker():
    """HK 节点逻辑：持久运行"""
    google = GoogleClient()
    
    # 🌟 关键优化：模型只加载一次
    print(f"🚀 正在初始化 Whisper 模型 ({Config.WHISPER_MODEL_SIZE})...")
    model = WhisperModel(
        Config.WHISPER_MODEL_SIZE, 
        device=Config.DEVICE, 
        compute_type=Config.COMPUTE_TYPE,
        cpu_threads=Config.CPU_THREADS # 🚀 使用配置中的线程数
    )

    while True:
        try:
            print("\n" + "="*30)
            print(f"📅 轮询触发: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            production_sheet = google.get_production_sheet()
            records = production_sheet.get_all_values()
            processed_count = 0
            
            # 1. 扫描所有待处理任务
            eligible_tasks = []
            zombie_rows = []
            for i, row in enumerate(records[1:], start=2):
                status = str(row[2]).strip() if len(row) > 2 else ""
                transcript_cell = str(row[4]).strip() if len(row) > 4 else ""
                
                if status in ["音频已就绪", "音视频已就绪"]:
                    if transcript_cell:
                        zombie_rows.append(i)
                    else:
                        eligible_tasks.append((i, row))

            print(f"📋 待处理队列: {len(zombie_rows)} 个僵尸行, {len(eligible_tasks)} 个待转录任务")

            # 2. 批量处理僵尸行 (状态纠偏)
            if zombie_rows:
                print(f"🔎 正在批量翻转 {len(zombie_rows)} 个僵尸行状态...")
                # 构造批量更新数据: [{range: 'C2', values: [['等待处理']]}, ...]
                batch_updates = []
                for row_idx in zombie_rows:
                    batch_updates.append({
                        'range': f'C{row_idx}',
                        'values': [['等待处理']]
                    })
                
                # gspread 批量更新
                try:
                    production_sheet.batch_update(batch_updates)
                    print(f"✅ 成功批量纠偏 {len(zombie_rows)} 行状态")
                except Exception as e:
                    print(f"⚠️ 批量更新失败，降级为逐行更新: {e}")
                    for row_idx in zombie_rows:
                        production_sheet.update_cell(row_idx, 3, "等待处理")
                        time.sleep(0.5)

            # 3. 处理转录任务
            for i, row in eligible_tasks:
                if processed_count >= Config.TRANSCRIPTION_LIMIT:
                    print(f"🛑 已达到本轮处理上限 ({Config.TRANSCRIPTION_LIMIT} 条)，进入下一轮。")
                    break
                    
                video_id = row[1]
                print(f"--- 正在转录 [{processed_count+1}/{Config.TRANSCRIPTION_LIMIT}]: {video_id} ---")
                
                audio_dir = Config.RCLONE_MOUNT_PATH if Config.RCLONE_MOUNT_PATH else Config.LOCAL_TEMP_DIR
                audio_path = os.path.join(audio_dir, f"{video_id}.mp3")
                
                if not os.path.exists(audio_path):
                    print(f"⚠️ 找不到文件: {audio_path}")
                    continue

                try:
                    segments, _ = model.transcribe(audio_path, beam_size=5)
                    final_text = " ".join([s.text for s in segments])
                    
                    # 写入字幕并更新状态 (使用批量方式更快)
                    production_sheet.batch_update([
                        {'range': f'E{i}', 'values': [[final_text]]},
                        {'range': f'C{i}', 'values': [['等待处理']]}
                    ])
                    print(f"✅ 完成行 {i}")
                    processed_count += 1
                except Exception as te:
                    print(f"❌ 转录失败 {video_id}: {te}")
                    production_sheet.update_cell(i, 3, "转录失败")

            print(f"☕ 本轮处理完毕，休眠 60 秒...")
            time.sleep(60)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"⚠️ 运行时异常: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run_worker()
