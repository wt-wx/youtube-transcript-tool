import os
import time
from faster_whisper import WhisperModel
from src.core.config import Config
from src.core.google_api import GoogleClient

def transcribe_and_fill():
    """HK 节点逻辑：翻译官"""
    print("🚀 HK 转录节点启动 (已模块化)，正在扫描就绪音频...")
    
    google = GoogleClient()
    production_sheet = google.get_production_sheet()
    
    # 延迟加载模型以优化内存
    print(f"正在加载 Whisper 模型 ({Config.WHISPER_MODEL_SIZE})...")
    model = WhisperModel(
        Config.WHISPER_MODEL_SIZE, 
        device=Config.DEVICE, 
        compute_type=Config.COMPUTE_TYPE
    )

    records = production_sheet.get_all_values()
    processed_count = 0
    
    for i, row in enumerate(records[1:], start=2):
        if processed_count >= Config.TRANSCRIPTION_LIMIT:
            break
            
        video_id = row[1]
        status = row[2] if len(row) > 2 else ""
        transcript_cell = row[4] if len(row) > 4 else ""
        
        # 仅处理状态为【音频已就绪】且 E 列为空的行
        if status == "音频已就绪" and not transcript_cell:
            print(f"\n--- 正在转录: {video_id} ---")
            
            # 音频路径：根据配置决定
            audio_dir = Config.RCLONE_MOUNT_PATH if Config.RCLONE_MOUNT_PATH else Config.LOCAL_TEMP_DIR
            audio_path = os.path.join(audio_dir, f"{video_id}.mp3")
            
            if not os.path.exists(audio_path):
                print(f"⚠️ 音频文件未找到: {audio_path}，可能同步延迟，跳过。")
                continue

            try:
                # 推理转录
                segments, info = model.transcribe(
                    audio_path, 
                    beam_size=5, 
                    initial_prompt="以下是关于科技、生活或时政的中文对话，请使用简体中文输出。"
                )
                
                full_text = []
                for segment in segments:
                    full_text.append(segment.text)
                
                final_text = " ".join(full_text)
                
                # 回填表格
                production_sheet.update_cell(i, 5, final_text)
                production_sheet.update_cell(i, 3, "等待处理") 
                print(f"✅ 转录完成并已更新表格 (行 {i})")
                
                processed_count += 1
                
            except Exception as e:
                print(f"❌ 转录失败 {video_id}: {str(e)}")
                production_sheet.update_cell(i, 3, "转录失败")

    if processed_count == 0:
        print("暂无就绪音频。")
    else:
        print(f"\n任务处理完毕。共转录 {processed_count} 条。")

if __name__ == "__main__":
    while True:
        try:
            transcribe_and_fill()
            print("\n进入休眠，等待下一轮 (5分钟)...")
            time.sleep(300)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"故障恢复中: {e}")
            time.sleep(300)
