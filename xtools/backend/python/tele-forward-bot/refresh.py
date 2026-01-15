import dropbox
import sys

APP_KEY = "xiqvlwoijni1jzz"
APP_SECRET = "1slbjrcclpdja5o"
REDIRECT_URI = "https://work-1-vudwpetebczpzfow.prod-runtime.all-hands.dev/callback"

def get_refresh_token():
    print("--- Simple Dropbox Refresh Token Generator ---")
    
    # Initialize the OAuth flow handler
    auth_flow = dropbox.oauth.DropboxOAuth2Flow(
        consumer_key=APP_KEY,
        redirect_uri=REDIRECT_URI,
        session={},
        csrf_token_session_key='dropbox-auth-csrf-token',
        consumer_secret=APP_SECRET,
        token_access_type='offline'
    )

    # Generate the authorization URL
    authorize_url = auth_flow.start()
    
    print(f"\n🚀 Authorization URL:")
    print(authorize_url)
    print(f"\n📋 Visit this URL in your browser and authorize the app.")
    print(f"🔗 The OAuth receiver server will capture the code automatically.")
    print(f"💡 Check the OAuth receiver logs for the authorization code.")
    
    # Get the state for later use
    state = auth_flow.session.get('dropbox-auth-csrf-token', '')
    print(f"\n🔑 State token: {state}")
    
    # Wait for manual input of the code
    print(f"\n📝 Enter the authorization code from the OAuth receiver:")
    auth_code = input("Code: ").strip()
    
    if not auth_code:
        print("❌ No code entered. Exiting.")
        return
    
    try:
        # Exchange the code for tokens
        result = auth_flow.finish({"code": auth_code, "state": state})
        
        print(f"\n🎉 SUCCESS! Refresh Token Generated:")
        print(f"🔐 REFRESH TOKEN: {result.refresh_token}")
        print(f"🔑 ACCESS TOKEN: {result.access_token}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == '__main__':
    get_refresh_token()