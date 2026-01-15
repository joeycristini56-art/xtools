from flask import Flask, request
import sys

app = Flask(__name__)

@app.route('/callback')
def oauth_callback():
    # Get the authorization code from the callback
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        print(f"❌ OAuth Error: {error}")
        return f"<h1>OAuth Error</h1><p>{error}</p>", 400
    
    if code:
        print(f"✅ Authorization Code Received: {code}")
        print(f"🔑 State: {state}")
        return f"""
        <h1>✅ Authorization Successful!</h1>
        <p><strong>Authorization Code:</strong> <code>{code}</code></p>
        <p><strong>State:</strong> <code>{state}</code></p>
        <p>Copy the authorization code above and paste it into the refresh token script.</p>
        """
    else:
        print("❌ No authorization code received")
        return "<h1>❌ No Authorization Code</h1><p>No code parameter found in callback.</p>", 400

@app.route('/')
def home():
    return "<h1>OAuth Receiver Server</h1><p>Waiting for Dropbox OAuth callback...</p>"

if __name__ == '__main__':
    print("🚀 Starting OAuth receiver server on port 12000...")
    print("🔗 Callback URL: https://work-1-vudwpetebczpzfow.prod-runtime.all-hands.dev/callback")
    app.run(host='0.0.0.0', port=12000, debug=False)