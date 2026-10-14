#!/usr/bin/env python3
"""
ZMINE Dedicated Auto-Registration Tool
Features:
- Natural Indonesian display names generator (nisa, anis, yani, etc.)
- Per-account Tor circuit stream isolation (distinct exit IPs)
- Auto-registers via specified referral code (default 4VN2PNKK)
- Auto-activates 24-hour free mining session
- Auto-solves all 12 daily SI tasks (Regex Rule Engine + Local AI fallback)
- Appends to accounts.json & syncs credentials.txt
- Optional Telegram document dispatch
"""

import os
import sys
import json
import time
import random
import argparse
import urllib.request
from pathlib import Path
import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from solver import solve_task

# Directory and Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("ZMINE_DATA_DIR", BASE_DIR)
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
CREDENTIALS_FILE = os.path.join(DATA_DIR, "credentials.txt")

TOR_HOST = os.environ.get("TOR_PROXY_HOST", "127.0.0.1")
TOR_PORT = int(os.environ.get("TOR_PROXY_PORT", "9050"))
DEFAULT_REF = os.environ.get("ZMINE_DEFAULT_REF", "4VN2PNKK")

AI_URL = os.environ.get("ZMINE_AI_URL", "http://127.0.0.1:20128/v1/chat/completions")
AI_KEY = os.environ.get("ZMINE_AI_KEY", "")
AI_MODEL = os.environ.get("ZMINE_AI_MODEL", "ag/gemini-3.8-flash-low")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Auto-detect local 9Router key if on local system and key not explicitly set in env
if not AI_KEY:
    router_db = os.path.expanduser("~/.9router/db/data.sqlite")
    if os.path.exists(router_db):
        try:
            import sqlite3
            con = sqlite3.connect(router_db)
            AI_KEY = con.cursor().execute("SELECT key FROM apiKeys LIMIT 1").fetchone()[0]
        except Exception:
            pass

FIRST_NAMES = [
    "nisa", "anis", "yani", "dinda", "sari", "putri", "laras", "mega", "maya", "tari",
    "indah", "tiara", "citra", "ayu", "ratna", "wulan", "nadia", "rina", "fitri", "dewi",
    "fajar", "bayu", "rizki", "dimas", "tio", "adit", "angga", "bima", "rendy", "gilang",
    "ari", "bagus", "ilham", "dika", "alif", "yusuf", "kevin", "andre", "rio", "deni"
]

LAST_NAMES = [
    "pratama", "lestari", "ramadhani", "wulandari", "aditya", "saputra", "savitri", "kusuma",
    "permata", "utami", "hidayat", "nugroho", "santoso", "wijaya", "mahendra", "firmansyah",
    "prasetyo", "setiawan", "gunawan", "subekti", "syahputra", "cahyani", "anggraeni", "oktaviani"
]


def generate_natural_name(existing_names: set | None = None) -> str:
    if existing_names is None:
        existing_names = set()
    for _ in range(100):
        pat = random.choice([1, 2, 3])
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        if pat == 1:
            name = f"{fn}_{ln}"
        elif pat == 2:
            num = random.randint(11, 99)
            name = f"{fn}_{ln}{num}"
        else:
            fn2 = random.choice([n for n in FIRST_NAMES if n != fn])
            name = f"{fn}_{fn2}"
        name = name[:24]
        if name not in existing_names:
            return name
    return f"{random.choice(FIRST_NAMES)}_{random.randint(1000, 9999)}"


def load_accounts() -> list:
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_accounts(accounts: list) -> None:
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)
    sync_credentials_txt(accounts)


def sync_credentials_txt(accounts: list) -> None:
    lines = [
        "=" * 60,
        "ZMINE MULTI-ACCOUNT BACKUP & CREDENTIALS",
        "=" * 60,
        f"Total Accounts: {len(accounts)}",
        "=" * 60,
        "",
    ]
    for i, acc in enumerate(accounts, 1):
        u = acc.get("user", {})
        lines.append(f"[{i}] ACCOUNT: {u.get('displayName')} (Handle: {u.get('handle')})")
        lines.append(f"User ID: {u.get('id')}")
        lines.append(f"Tor Circuit / IP: {acc.get('torUserId')} / {acc.get('torExitIp')}")
        lines.append(f"Login Key:")
        lines.append(f"  {acc.get('loginKey')}")
        lines.append(f"Recovery Phrase (24 Words):")
        lines.append(f"  {acc.get('recoveryPhrase')}")
        lines.append(f"Session Cookie:")
        lines.append(f"  zmine_session={acc.get('sessionCookie')}")
        lines.append(
            f"Status: Mining {acc.get('miningStatus')} | Hashpower: {acc.get('hashpower')} | Tasks: {acc.get('tasksCompleted')}"
        )
        lines.append(f"Expires: {acc.get('sessionExpiresAt')}")
        lines.append("-" * 60)
        lines.append("")

    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def send_telegram_doc() -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        if Path(CREDENTIALS_FILE).exists():
            boundary = f"----WebKitFormBoundaryZmine{int(time.time())}"
            body = []
            body.append(f"--{boundary}".encode())
            body.append(f'Content-Disposition: form-data; name="chat_id"'.encode())
            body.append(b"")
            body.append(str(TELEGRAM_CHAT_ID).encode())
            body.append(f"--{boundary}".encode())
            body.append(f'Content-Disposition: form-data; name="caption"'.encode())
            body.append(b"")
            body.append(b"ZMINE Accounts Backup (Updated)")
            body.append(f"--{boundary}".encode())
            body.append(
                f'Content-Disposition: form-data; name="document"; filename="zmine_accounts_credentials.txt"'.encode()
            )
            body.append(b"Content-Type: text/plain")
            body.append(b"")
            body.append(Path(CREDENTIALS_FILE).read_bytes())
            body.append(f"--{boundary}--".encode())
            body.append(b"")
            payload = b"\r\n".join(body)
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument",
                data=payload,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            urllib.request.urlopen(req, timeout=10)
            print("  [Telegram] Document sent successfully.")
    except Exception as e:
        print(f"  [Telegram send error] {e}")


def register_one_account(referral_code: str, skip_tasks: bool = False) -> dict | None:
    accounts = load_accounts()
    existing_names = {a.get("user", {}).get("displayName") for a in accounts}
    display_name = generate_natural_name(existing_names)
    tor_user = f"tor_acc_{int(time.time())}_{random.randint(100, 999)}"
    proxy = f"socks5://{tor_user}:torpass123@{TOR_HOST}:{TOR_PORT}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://zmine.si",
        "Referer": f"https://zmine.si/register?ref={referral_code}",
    }

    print(f"\n========================================")
    print(f"Registering Account: {display_name}")
    print(f"Tor Circuit: {tor_user}")
    print(f"Referral Target: {referral_code}")
    print(f"========================================")

    with httpx.Client(proxy=proxy, headers=headers, timeout=30.0) as client:
        # 1. Tor Exit IP check
        try:
            ip = client.get("https://api.ipify.org?format=json").json().get("ip")
            print(f"  Tor Exit IP: {ip}")
        except Exception as e:
            print(f"  Tor IP check error: {e}")
            ip = "unknown_tor"

        # 2. Hit registration page
        r0 = client.get(f"https://zmine.si/register?ref={referral_code}")
        if r0.status_code != 200:
            print(f"  Warning: GET /register returned {r0.status_code}")

        # 3. Submit register
        payload = {"displayName": display_name, "referralCode": referral_code}
        r1 = client.post("https://zmine.si/api/v1/auth/register", json=payload)
        if r1.status_code not in [200, 201]:
            print(f"  Registration FAILED ({r1.status_code}): {r1.text}")
            return None

        reg_data = r1.json()
        user_info = reg_data["user"]
        login_key = reg_data["loginKey"]
        recovery_phrase = reg_data["recoveryPhrase"]
        session_cookie = client.cookies.get("zmine_session")
        print(f"  SUCCESS: Handle={user_info['handle']} | ID={user_info['id']}")
        print(f"  LoginKey: {login_key[:18]}...")

        # 4. Activate Mining
        client.headers.update({"Referer": "https://zmine.si/app/mine"})
        rm = client.post("https://zmine.si/api/v1/mining/activate")
        mining_status = "active" if rm.status_code == 200 else "inactive"
        print(f"  Mining 24h Session Activated: {rm.status_code == 200}")

        # 5. Solve Daily Tasks
        tasks_completed = "0/12"
        if not skip_tasks:
            client.headers.update({"Referer": "https://zmine.si/app/si"})
            print("  Solving 12 Daily Tasks...")
            while True:
                rt = client.get("https://zmine.si/api/v1/si/tasks/next")
                if rt.status_code != 200:
                    print(f"  Task fetch status: {rt.status_code}")
                    break
                t_data = rt.json()
                stats = t_data.get("stats", {})
                correct = stats.get("correctToday", 0)
                cap = stats.get("cap", 12)
                if correct >= cap:
                    tasks_completed = f"{correct}/{cap}"
                    print(f"  Daily Tasks Cap Reached: {tasks_completed}")
                    break
                task = t_data.get("task")
                if not task:
                    break
                prompt = task["prompt"]
                options = task["options"]
                token = task["token"]

                ans, method = solve_task(prompt, options, AI_URL, AI_KEY, AI_MODEL)

                # Essential delay: server checks issued timestamp (tooFast anti-bot protection)
                time.sleep(3.6)
                client.post(
                    "https://zmine.si/api/v1/si/tasks/answer",
                    json={"token": token, "answer": ans},
                )
                time.sleep(1.2)
                print(f"    Task {correct + 1}/{cap} completed.")

        # 6. Fetch final overview
        rf = client.get("https://zmine.si/api/v1/mining/overview").json()
        hp = rf.get("hashpower", {}).get("totalMh", "0")
        hashpower_str = f"{int(hp):,} Mh" if str(hp).isdigit() else f"{hp} Mh"
        session_exp = rf.get("sessionExpiresAt")

        account_entry = {
            "user": user_info,
            "loginKey": login_key,
            "recoveryPhrase": recovery_phrase,
            "referralCodeUsed": referral_code,
            "sessionCookie": session_cookie,
            "torUserId": tor_user,
            "torExitIp": ip,
            "createdAt": rf.get("miner", {}).get("lastActivatedAt"),
            "miningStatus": mining_status,
            "sessionExpiresAt": session_exp,
            "hashpower": hashpower_str,
            "tasksCompleted": tasks_completed,
        }

        accounts.append(account_entry)
        save_accounts(accounts)
        print(f"  Saved account '{display_name}' to {ACCOUNTS_FILE}!")
        return account_entry


def main():
    parser = argparse.ArgumentParser(description="ZMINE Dedicated Registration Tool")
    parser.add_argument("--count", type=int, default=1, help="Number of accounts to create (default: 1)")
    parser.add_argument("--ref", type=str, default=DEFAULT_REF, help=f"Referral code (default: {DEFAULT_REF})")
    parser.add_argument("--skip-tasks", action="store_true", help="Skip solving daily tasks right after registration")
    args = parser.parse_args()

    print(f"Starting registration for {args.count} account(s) using ref '{args.ref}'...")
    created = 0
    for i in range(1, args.count + 1):
        print(f"\n[Batch {i}/{args.count}]")
        acc = register_one_account(args.ref, skip_tasks=args.skip_tasks)
        if acc:
            created += 1
        if i < args.count:
            time.sleep(5)

    print(f"\nFinished! Total new accounts created: {created}/{args.count}")
    send_telegram_doc()


if __name__ == "__main__":
    main()
