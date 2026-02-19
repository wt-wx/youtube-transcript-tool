import os
from dotenv import load_dotenv

# 加载 .env 变量
load_dotenv()

class Config:
    # Google Cloud 凭据
    CREDENTIALS_FILE = os.getenv('CREDENTIALS_FILE', 'credentials.json')
    
    # 表格配置
    SPREADSHEET_NAME = os.getenv('SPREADSHEET_NAME', 'YouTube_Blogger_Automation')
    SHEET_NAME = os.getenv('SHEET_NAME', 'Production')
    
    # Drive 配置
    DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID', '')
    RCLONE_MOUNT_PATH = os.getenv('RCLONE_MOUNT_PATH')
    
    # LA 节点参数
    RATE_LIMIT = os.getenv('DOWNLOAD_RATE_LIMIT', '5M')
    FETCH_LIMIT = int(os.getenv('FETCH_LIMIT', 10))
    MIN_DELAY = int(os.getenv('MIN_DELAY', 30))
    MAX_DELAY = int(os.getenv('MAX_DELAY', 120))
    
    # HK 节点参数
    WHISPER_MODEL_SIZE = os.getenv('WHISPER_MODEL_SIZE', 'medium')
    DEVICE = os.getenv('DEVICE', 'cpu')
    COMPUTE_TYPE = os.getenv('COMPUTE_TYPE', 'int8')
    TRANSCRIPTION_LIMIT = int(os.getenv('TRANSCRIPTION_LIMIT', 5))
    
    # 路径配置
    LOCAL_TEMP_DIR = os.getenv('LOCAL_TEMP_DIR', 'temp_audio')

    @classmethod
    def ensure_dirs(cls):
        """确保必要的本地目录存在"""
        if not os.path.exists(cls.LOCAL_TEMP_DIR):
            os.makedirs(cls.LOCAL_TEMP_DIR)
