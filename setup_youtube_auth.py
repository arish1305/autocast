
import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from src.core.config import settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def authenticate_youtube():
    print("Starting YouTube Authentication...")
    
    if not settings.YOUTUBE_CLIENT_ID or not settings.YOUTUBE_CLIENT_SECRET:
        print("ERROR: YOUTUBE_CLIENT_ID or YOUTUBE_CLIENT_SECRET not set in .env")
        return

    # specific structure required by google-auth-oauthlib
    client_config = {
        "installed": {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "project_id": "autocast-project", # Placeholder, doesn't matter for this flow
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "redirect_uris": ["http://localhost"]
        }
    }

    flow = InstalledAppFlow.from_client_config(
        client_config, SCOPES
    )
    
    print("Please check your browser to authorize the application.")
    creds = flow.run_local_server(port=0)
    
    with open("token.pickle", "wb") as token:
        pickle.dump(creds, token)
    
    print("Authentication successful! 'token.pickle' has been saved.")

if __name__ == "__main__":
    authenticate_youtube()
