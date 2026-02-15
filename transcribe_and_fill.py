import os
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from faster_whisper import WhisperModel
from dotenv import load_dotenv

load_dotenv()

# --- 配置加载 ---
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'YouTube_Blogger_Automation')
SHEET_NAME = os.getenv('SHEET_NAME', 'Production')
RCLONE_MOUNT_PATH = os.getenv('RCLONE_MOUNT_PATH')
WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'medium')
DEVICE = os.getenv('DEVICE', 'cpu')
COMPUTE_TYPE = os.getenv('COMPUTE_TYPE', 'int8')
TRANSCRIPTION_LIMIT = int(os.getenv('TRANSCRIPTION_LIMIT', 5))

# --- 初始化 ---
print(f"正在加载 Whisper 模型 ({WHISPER_MODEL_SIZE})...")
model = WhisperModel(WHISPER_MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
gc = gspread.authorize(creds)
spreadsheet = gc.open(SPREADSHEET_NAME)
production_sheet = spreadsheet.worksheet(SHEET_NAME)

def transcribe_and_fill():
    """HK 节点核心逻辑：翻译官"""
    print("🚀 HK 转录节点启动，正在扫描就绪音频...")
    
    records = production_sheet.get_all_values()
    processed_count = 0
    
    for i, row in enumerate(records[1:], start=2):
        if processed_count >= TRANSCRIPTION_LIMIT:
            break
            
        video_id = row[1]
        status = row[2] if len(row) > 2 else ""
        transcript_cell = row[4] if len(row) > 4 else ""
        
        # 仅处理状态为【音频已就绪】且 E 列为空的行
        if status == "音频已就绪" and not transcript_cell:
            print(f"\n--- 正在转录: {video_id} ---")
            
            # 音频路径：必须在 Rclone 挂载路径下
            audio_dir = RCLONE_MOUNT_PATH if RCLONE_MOUNT_PATH else "downloads"
            audio_path = os.path.join(audio_dir, f"{video_id}.mp3")
            
            if not os.path.exists(audio_path):
                print(f"⚠️ 音频文件未找到: {audio_path}，可能同步延迟，跳过。")
                continue

            try:
                # 推理转录
                # initial_prompt 针对中文视频减少繁简错误
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
                production_sheet.update_cell(i, 3, "等待处理") # 状态流转回给 Apps Script
                print(f"✅ 转录完成并已更新表格 (行 {i})")
                
                # 物理删除本地音频缓存（PRD 风险规避要求）
                # 注意：如果是 Rclone 挂载，删除本地文件也会同步删除云端文件
                # 如果你想永久保留，请注释掉下面这两行
                # os.remove(audio_path)
                # print(f"清理本地音频缓存: {video_id}.mp3")
                
                processed_count += 1
                
            except Exception as e:
                print(f"❌ 转录失败 {video_id}: {str(e)}")
                production_sheet.update_cell(i, 3, "转录失败")

    if processed_count == 0:
        print("暂无就绪音频。")
    else:
        print(f"\n本次转录任务处理完毕。共处理 {processed_count} 条。")

if __name__ == "__main__":
    while True:
        try:
            transcribe_and_fill()
            print("\n进入休眠，等待下一轮扫描 (5分钟)...")
            time.sleep(300)
        except KeyboardInterrupt:
            print("\n程序由用户停止。")
            break
        except Exception as e:
            print(f"\n运行时发生未知错误: {e}，5分钟后重试...")
            time.sleep(300)
