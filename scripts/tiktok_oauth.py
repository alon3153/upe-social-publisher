#!/usr/bin/env python3
"""TikTok OAuth flow — interactive setup to get user access + refresh tokens.

Usage:
  1. Set TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET in .env
  2. Make sure your TikTok app has redirect URI:
     https://alon3153.github.io/upe-social-publisher/tiktok-callback.html
  3. Run: python3 scripts/tiktok_oauth.py
  4. Browser opens → log in & authorize → callback page shows code
  5. Paste code into terminal
  6. Tokens saved into .env (TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN, TIKTOK_OPEN_ID)
"""
import os
import sys
import secrets
import webbrowser
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from publishers.tiktok import build_authorize_url, exchange_code_for_token

REDIRECT_URI = "https://alon3153.github.io/upe-social-publisher/tiktok-callback.html"
SCOPE = "user.info.basic,video.upload,video.publish"
ENV_PATH = ROOT / ".env"


def update_env(updates: dict) -> None:
    """Upsert keys in the .env file."""
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()
    else:
        lines = []
    keys_handled = set()
    new_lines = []
    for line in lines:
        replaced = False
        for k, v in updates.items():
            if line.startswith(f"{k}="):
                new_lines.append(f"{k}={v}")
                keys_handled.add(k)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)
    for k, v in updates.items():
        if k not in keys_handled:
            new_lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n")


def main():
    client_key = os.environ.get("TIKTOK_CLIENT_KEY")
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET")
    if not client_key or not client_secret:
        print("❌ Missing TIKTOK_CLIENT_KEY or TIKTOK_CLIENT_SECRET in .env")
        print()
        print("Setup steps:")
        print("  1. Go to https://developers.tiktok.com")
        print("  2. Sign in with your TikTok account (@alonouaknine)")
        print("  3. Manage apps → Create app → fill basic info")
        print("  4. Add product: Login Kit + Content Posting API")
        print(f"  5. Add redirect URI: {REDIRECT_URI}")
        print("  6. Request scopes: user.info.basic, video.upload, video.publish")
        print("  7. Copy Client Key + Client Secret")
        print("  8. Add to .env:")
        print("       TIKTOK_CLIENT_KEY=...")
        print("       TIKTOK_CLIENT_SECRET=...")
        sys.exit(1)

    state = secrets.token_urlsafe(16)
    url = build_authorize_url(client_key, REDIRECT_URI, SCOPE, state)
    print(f"🔗 Opening browser to authorize…")
    print(f"   {url}")
    print()
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print(f"📋 After authorizing, the page at:")
    print(f"   {REDIRECT_URI}")
    print(f"   will display a code. Copy it here.")
    print()
    code = input("Paste authorization code: ").strip()
    if not code:
        print("❌ No code provided")
        sys.exit(1)

    print(f"🔄 Exchanging code for tokens…")
    tokens = exchange_code_for_token(client_key, client_secret, code, REDIRECT_URI)

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")
    open_id = tokens.get("open_id", "")
    scope = tokens.get("scope", "")
    expires_in = tokens.get("expires_in", 0)

    print(f"✅ Got tokens! Saving to .env")
    update_env({
        "TIKTOK_ACCESS_TOKEN": access_token,
        "TIKTOK_REFRESH_TOKEN": refresh_token,
        "TIKTOK_OPEN_ID": open_id,
        "TIKTOK_SCOPE": scope,
    })
    print(f"   open_id: {open_id}")
    print(f"   scope: {scope}")
    print(f"   access expires in: {expires_in}s ({expires_in // 3600}h)")
    print()
    print("🎉 Setup complete. You can now run scripts/publish_ab_dental_tiktok.py")


if __name__ == "__main__":
    main()
