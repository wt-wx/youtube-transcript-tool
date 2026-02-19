import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from faster_whisper import WhisperModel
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# 加载 .env 变量
load_dotenv()

# ================= 配置区 (从 .env 读取) =================
CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')
SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'YouTube_Blogger_Automation')
SHEET_NAME = os.getenv('SHEET_NAME', 'Production')

# Google Drive 文件夹 ID
DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID', '') 

# Whisper 配置
WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'base')
DEVICE = os.getenv('DEVICE', 'cpu')
ComputeType = os.getenv('COMPUTE_TYPE', 'int8')

# 本地临时目录
LOCAL_TEMP_DIR = os.getenv('LOCAL_TEMP_DIR', 'temp_audio')
if not os.path.exists(LOCAL_TEMP_DIR):
    os.makedirs(LOCAL_TEMP_DIR)

# ================= 授权 & 初始化 =================
# 1. 基础凭据加载
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)

# 2. Google Sheets 初始化
gc = gspread.authorize(creds)
spreadsheet = gc.open(SPREADSHEET_NAME)
production_sheet = spreadsheet.worksheet(SHEET_NAME)

# 3. Google Drive API 初始化 (用于上传文件)
drive_service = build('drive', 'v3', credentials=creds)

# 4. 加载 Whisper 模型
print(f"正在加载 Whisper 模型 ({WHISPER_MODEL_SIZE})...")
model = WhisperModel(WHISPER_MODEL_SIZE, device=DEVICE, compute_type=ComputeType)

# ================= 核心功能 =================

def upload_to_drive(local_path, filename):
    """将文件上传到 Google Drive"""
    print(f"正在上传到 Google Drive: {filename}...")
    
    file_metadata = {'name': filename}
    if DRIVE_FOLDER_ID:
        file_metadata['parents'] = [DRIVE_FOLDER_ID]
    
    media = MediaFileUpload(local_path, mimetype='audio/mpeg', resumable=True)
    
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    
    print(f"✅ 上传成功，文件 ID: {file.get('id')}")
    return file.get('id')

def download_audio(video_url, video_id):
    """下载音频"""
    local_path = os.path.join(LOCAL_TEMP_DIR, f"{video_id}.mp3")
    
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

def drive_pipeline(limit=5):
    """Google Drive 版自动化流水线"""
    records = production_sheet.get_all_values()
    api = YouTubeTranscriptApi()
    
    processed_count = 0
    for i, row in enumerate(records[1:], start=2):
        if processed_count >= limit:
            break
            
        video_url = row[0]
        video_id = row[1]
        status = row[2] if len(row) > 2 else ""
        transcript_cell = row[4] if len(row) > 4 else ""
        
        # 处理流程
        if video_id and not transcript_cell:
            print(f"\n--- 正在处理: {video_id} ---")
            
            try:
                # 尝试抓取 API 字幕
                try:
                    transcript_obj = api.fetch(video_id, languages=['zh-Hans', 'zh-Hant', 'en'])
                    final_text = " ".join([t['text'] for t in transcript_obj.to_raw_data()])
                    source_mark = "官方字幕"
                except Exception:
                    # AI 流程
                    print("官方字幕缺失，开始 AI + Google Drive 流程...")
                    local_audio = download_audio(video_url, video_id)
                    
                    # 上传到 Google Drive
                    upload_to_drive(local_audio, f"{video_id}.mp3")
                    
                    # AI 转录
                    final_text = transcribe_audio(local_audio)
                    source_mark = f"AI(Whisper-{WHISPER_MODEL_SIZE})"
                    
                    # 清理本地 (Drive 已存，本地可删)
                    # os.remove(local_audio)

                # 更新表格
                production_sheet.update_cell(i, 5, final_text)
                production_sheet.update_cell(i, 3, f"完成 ({source_mark})")
                print(f"✅ 行 {i} 处理完成")
                processed_count += 1

            except Exception as e:
                print(f"❌ 运行报错: {str(e)}")
                production_sheet.update_cell(i, 3, "处理出错")

if __name__ == "__main__":
    drive_pipeline(limit=5)
