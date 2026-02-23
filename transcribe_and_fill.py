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
        cpu_threads=1 # 限制线程，防止瞬时内存爆发
    )

    while True:
        try:
            print("\n" + "="*30)
            print(f"📅 轮询触发: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            production_sheet = google.get_production_sheet()
            records = production_sheet.get_all_values()
            processed_count = 0
            
            for i, row in enumerate(records[1:], start=2):
                if processed_count >= Config.TRANSCRIPTION_LIMIT:
                    break
                    
                video_id = row[1]
                status = row[2] if len(row) > 2 else ""
                transcript_cell = row[4] if len(row) > 4 else ""
                
                if status == "音频已就绪" and not transcript_cell:
                    print(f"--- 正在转录: {video_id} ---")
                    audio_dir = Config.RCLONE_MOUNT_PATH if Config.RCLONE_MOUNT_PATH else Config.LOCAL_TEMP_DIR
                    audio_path = os.path.join(audio_dir, f"{video_id}.mp3")
                    
                    if not os.path.exists(audio_path):
                        print(f"⚠️ 找不到文件: {audio_path}")
                        continue

                    segments, _ = model.transcribe(audio_path, beam_size=5)
                    final_text = " ".join([s.text for s in segments])
                    
                    production_sheet.update_cell(i, 5, final_text)
                    production_sheet.update_cell(i, 3, "等待处理") 
                    print(f"✅ 完成行 {i}")
                    processed_count += 1

            print(f"休眠中，等待下一轮...")
            time.sleep(300)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"⚠️ 运行时异常: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_worker()
