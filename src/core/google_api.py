import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from src.core.config import Config

class GoogleClient:
    _instance = None
    _creds = None

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
        cls._creds = ServiceAccountCredentials.from_json_keyfile_name(
            Config.CREDENTIALS_FILE, scope
        )

    def get_sheets_client(self):
        return gspread.authorize(self._creds)

    def get_drive_service(self):
        return build('drive', 'v3', credentials=self._creds)

    def get_production_sheet(self):
        gc = self.get_sheets_client()
        spreadsheet = gc.open(Config.SPREADSHEET_NAME)
        return spreadsheet.worksheet(Config.SHEET_NAME)

    def upload_to_drive(self, local_path, filename):
        """将文件上传至 Google Drive 指定文件夹"""
        drive_service = self.get_drive_service()
        file_metadata = {'name': filename}
        
        if Config.DRIVE_FOLDER_ID:
            file_metadata['parents'] = [Config.DRIVE_FOLDER_ID]
            
        media = MediaFileUpload(local_path, mimetype='audio/mpeg', resumable=True)
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return file.get('id')
