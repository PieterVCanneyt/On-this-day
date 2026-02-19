import json, os
from dotenv import load_dotenv
from google.oauth2 import service_account
import google.auth.transport.requests

load_dotenv()
info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
print("Key ID in use:", info.get("private_key_id"))

creds = service_account.Credentials.from_service_account_info(info, scopes=[
    "https://www.googleapis.com/auth/documents",
])
creds.refresh(google.auth.transport.requests.Request())
print("Token acquired successfully:", creds.token[:20], "...")