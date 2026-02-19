import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from faster_whisper import WhisperModel
from google.cloud import storage

# ================= 配置区 =================
CREDENTIALS_FILE = 'credentials.json'  # 你的服务账号 JSON
SPREADSHEET_NAME = "YouTube_Blogger_Automation"
SHEET_NAME = "Production"

# Google Cloud Storage 配置
GCS_BUCKET_NAME = "your-bucket-name"  # 【需修改】你的存储桶名称

# Whisper 配置
WHISPER_MODEL_SIZE = "base"
DEVICE = "cpu"
ComputeType = "int8"

# 本地临时目录 (仅用于转录中转)
LOCAL_TEMP_DIR = "temp_audio"
if not os.path.exists(LOCAL_TEMP_DIR):
    os.makedirs(LOCAL_TEMP_DIR)

# ================= 授权 & 初始化 =================
# 1. Google Sheets & Drive 授权
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
gc = gspread.authorize(creds)
spreadsheet = gc.open(SPREADSHEET_NAME)
production_sheet = spreadsheet.worksheet(SHEET_NAME)

# 2. Google Cloud Storage 客户端初始化
# 直接复用同一个 credentials.json (需确保该服务账号有 Storage Admin/Object Creator 权限)
storage_client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
bucket = storage_client.bucket(GCS_BUCKET_NAME)

# 3. 加载 Whisper 模型
print(f"正在加载 Whisper 模型 ({WHISPER_MODEL_SIZE})...")
model = WhisperModel(WHISPER_MODEL_SIZE, device=DEVICE, compute_type=ComputeType)

# ================= 核心功能 =================

def upload_to_gcs(local_path, destination_blob_name):
    """将文件上传到 Google Cloud Storage"""
    print(f"正在上传到 GCS: {destination_blob_name}...")
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(local_path)
    print(f"✅ 上传成功.")

def download_audio(video_url, video_id):
    """使用 yt-dlp 下载音频流到本地临时目录"""
    output_filename = f"{video_id}.mp3"
    local_path = os.path.join(LOCAL_TEMP_DIR, output_filename)
    
    # yt-dlp 配置
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'outtmpl': os.path.join(LOCAL_TEMP_DIR, f"{video_id}.%(ext)s"),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    print(f"正在下载音频: {video_id}...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    
    return local_path

def transcribe_audio(audio_path):
    """AI 转录"""
    print(f"正在进行 AI 转录...")
    segments, info = model.transcribe(audio_path, beam_size=5)
    full_text = []
    for segment in segments:
        full_text.append(segment.text)
    return " ".join(full_text)

def gcs_pipeline(limit=5):
    """云端流水线"""
    records = production_sheet.get_all_values()
    api = YouTubeTranscriptApi()
    
    processed_count = 0
    for i, row in enumerate(records[1:], start=2):
        if processed_count >= limit:
            break
            
        video_url = row[0]
        video_id = row[1]
        transcript_cell = row[4] if len(row) > 4 else ""
        
        if video_id and not transcript_cell:
            print(f"\n--- 正在处理: {video_id} ---")
            
            try:
                # 尝试抓取官方字幕
                try:
                    transcript_obj = api.fetch(video_id, languages=['zh-Hans', 'zh-Hant', 'en'])
                    final_text = " ".join([t['text'] for t in transcript_obj.to_raw_data()])
                    source_mark = "官方字幕"
                except Exception:
                    # 官方字幕不可用 -> AI 流程
                    print("官方字幕缺失，开始 AI 流程...")
                    
                    # 1. 下载本地
                    local_audio = download_audio(video_url, video_id)
                    
                    # 2. 上传 GCS 持久化
                    gcs_blob_name = f"audio_archives/{video_id}.mp3"
                    upload_to_gcs(local_audio, gcs_blob_name)
                    
                    # 3. AI 转录
                    final_text = transcribe_audio(local_audio)
                    source_mark = f"AI(Whisper-{WHISPER_MODEL_SIZE})"
                    
                    # 4. 清理本地临时文件 (可选，不清理的话 LOCAL_TEMP_DIR 会越来越大)
                    # os.remove(local_audio)

                # 5. 更新 Google Sheets
                production_sheet.update_cell(i, 5, final_text)
                production_sheet.update_cell(i, 3, f"完成 ({source_mark})")
                print(f"✅ 行 {i} 处理完成")
                processed_count += 1

            except Exception as e:
                print(f"❌ 错误: {str(e)}")
                production_sheet.update_cell(i, 3, f"报错: {str(e)[:20]}")

if __name__ == "__main__":
    # 使用前请确保：
    # 1. 已经在 GCS 创建了 Bucket
    # 2. 修改了上面的 GCS_BUCKET_NAME
    # 3. credentials.json 里的服务账号对 Bucket 有写入权限
    gcs_pipeline(limit=5)
