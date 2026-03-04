import os
import gspread
from google.oauth2.credentials import Credentials
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from src.core.config import Config
from google.auth.transport.requests import Request

class GoogleClient:
    _instance = None
    _creds = None
    _user_creds = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GoogleClient, cls).__new__(cls)
            cls._init_creds()
        return cls._instance

    @classmethod
    def _init_creds(cls):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets"
        ]
        
        # 1. 优先使用个人用户 OAuth 授权的 token.json
        if os.path.exists('token.json'):
            cls._user_creds = Credentials.from_authorized_user_file('token.json', scope)
            
            # 🔄 自动刷新逻辑
            if not cls._user_creds.valid:
                if cls._user_creds.expired and cls._user_creds.refresh_token:
                    try:
                        cls._user_creds.refresh(Request())
                        # 保存刷新后的 token
                        with open('token.json', 'w') as token_file:
                            token_file.write(cls._user_creds.to_json())
                        print("✅ Google API Token 自动刷新成功")
                    except Exception as e:
                        print(f"❌ Google API Token 刷新失败: {e}")
                        # 如果刷新失败，清除 _user_creds 让它回退
                        cls._user_creds = None
        
        # 2. 回退使用 Service Account 凭据
        if not cls._user_creds and os.path.exists(Config.CREDENTIALS_FILE):
            cls._creds = ServiceAccountCredentials.from_json_keyfile_name(
                Config.CREDENTIALS_FILE, scope
            )
        
        if not cls._user_creds and not cls._creds:
            raise FileNotFoundError(f"未找到有效 token.json 或 {Config.CREDENTIALS_FILE}。")

    def get_sheets_client(self):
        if self._user_creds:
            return gspread.authorize(self._user_creds)
        return gspread.authorize(self._creds)

    def get_drive_service(self):
        if self._user_creds:
            return build('drive', 'v3', credentials=self._user_creds)
        return build('drive', 'v3', credentials=self._creds)

    def get_production_sheet(self):
        gc = self.get_sheets_client()
        spreadsheet = gc.open(Config.SPREADSHEET_NAME)
        return spreadsheet.worksheet(Config.SHEET_NAME)

    def upload_to_drive(self, local_path, filename, folder_id=None):
        """将文件上传至 Google Drive 指定文件夹"""
        drive_service = self.get_drive_service()
        file_metadata = {'name': filename}
        
        target_folder = folder_id if folder_id else Config.DRIVE_FOLDER_ID
        if target_folder:
            file_metadata['parents'] = [target_folder]
            
        media = MediaFileUpload(local_path, mimetype='audio/mpeg', resumable=True)
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        return file.get('id')
