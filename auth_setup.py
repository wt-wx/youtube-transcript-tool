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
        
        if creds and creds.expired and creds.refresh_token:
            print("🔄 token 已过期且无法自动刷新，即将尝试重新获取授权...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️  刷新令牌已失效 ({e})，正在切换到正式授权流程...")
                creds = None # 强制进入下面的 full flow
        
        if not creds or not creds.valid:
            if not os.path.exists('client_secret.json'):
                print("\n❌ 错误：未找到【client_secret.json】文件。")
                print("\n【准备步骤】:")
                print("1. 请打开 Google Cloud Console (https://console.cloud.google.com/)。")
                print("2. 点击左侧菜单「API 和服务」->「OAuth 权限请求页面」。")
                print("   - 选择「外部 (External)」，填写必填项(应用名称、支持电子邮件、开发者联系信息)后保存。")
                print("   - 在测试用户 (Test users) 中，务必添加你自己正在使用的 Gmail 邮箱。")
                print("3. 点击左侧菜单「凭据」-> 顶部「+ 创建凭据」-> 选择「OAuth 客户端 ID」。")
                print("   - 应用类型务必选择「桌面应用 (Desktop App)」。")
                print("4. 创建完成后，在列表右侧点击「下载 JSON」图标，将文件重命名为「client_secret.json」，放在本项目根目录中。")
                print("5. 准备好后，重新运行 python auth_setup.py 即可。\n")
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
