"""
One-time script to obtain a Google OAuth refresh token.
Run this locally, paste in your OAuth client credentials JSON when prompted,
then copy the printed refresh token into your .env and GitHub secrets.
"""

import json
import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

def main():
    client_secrets_path = input("Path to your downloaded OAuth client JSON file: ").strip()

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, scopes=SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n--- Copy these into your .env and GitHub secrets ---")
    print(f"GOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("-----------------------------------------------------")

if __name__ == "__main__":
    main()
