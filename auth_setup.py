import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

def main():
    creds = None
    
    print("🔑 正在检查本地授权...")
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        print("✅ 找到现有的 token.json 文件。")
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 token 已过期，正在自动刷新...")
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                print("\n❌ 错误：未找到【client_secret.json】文件。")
                print("\n【准备步骤】:")
                print("1. 请打开 Google Cloud Console (https://console.cloud.google.com/)。")
                print("2. 进入你的项目 -> 左侧菜单「API与服务」->「数据获取/OAuth 同意屏幕 (OAuth consent screen)」。")
                print("   - 选择「外部 (External)」，填写必填项后保存。(测试阶段即可，记得将你自己的邮箱加入 Test users)。")
                print("3. 点击左侧「凭据 (Credentials)」-> 顶部「创建凭据 (Create Credentials)」-> 选择「OAuth 客户端 ID」。")
                print("   - 应用类型务必选择「桌面应用 (Desktop App)」。")
                print("4. 创建完成后，点击右侧的下载按钮，将下载的 JSON 文件重命名为「client_secret.json」，放在本项目根目录中。")
                print("5. 准备好后，再次运行本脚本即可。\n")
                return
                
            print("🌐 即将拉起浏览器进行 Google 账号授权...")
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("💾 新的授权凭证已保存至 token.json！")
            
    print("\n🎉 授权大功告成！之后只需要确保 token.json 和代码一起运行即可，不再需要服务账号了。")

if __name__ == '__main__':
    main()
