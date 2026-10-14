#!/usr/bin/env python3
"""
ZMINE Multi-Account Automation Bot
Features:
- Multi-account management via accounts.json
- Per-account Tor circuit stream isolation (distinct exit IPs)
- Auto-login with loginKey if session cookie expires
- Daily mining activation (24-hour cycle)
- Automated SI Daily Tasks Solving (Regex Rule Engine + Local AI fallback)
- Anti-tooFast delay protection (>3.5s)
"""

import os
import sys
import json
import time
import argparse
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

AI_URL = os.environ.get("ZMINE_AI_URL", "http://127.0.0.1:20128/v1/chat/completions")
AI_KEY = os.environ.get("ZMINE_AI_KEY", "")
AI_MODEL = os.environ.get("ZMINE_AI_MODEL", "ag/gemini-3.8-flash-low")

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


def get_client_for_account(acc: dict) -> httpx.Client:
    tor_user = acc.get("torUserId", "tor_default")
    proxy = f"socks5://{tor_user}:torpass123@{TOR_HOST}:{TOR_PORT}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://zmine.si",
        "Referer": "https://zmine.si/app",
    }
    client = httpx.Client(proxy=proxy, headers=headers, timeout=30.0)
    session_cookie = acc.get("sessionCookie")
    if session_cookie:
        client.cookies.set("zmine_session", session_cookie)
    return client


def check_or_refresh_session(client: httpx.Client, acc: dict) -> bool:
    r = client.get("https://zmine.si/api/v1/mining/overview")
    if r.status_code == 401 or "authentication required" in r.text or "disabled" in r.text:
        login_key = acc.get("loginKey")
        print(f"  [{acc['user']['displayName']}] Session expired, re-authenticating with loginKey...")
        rl = client.post("https://zmine.si/api/v1/auth/login", json={"loginKey": login_key})
        if rl.status_code == 200:
            new_cookie = client.cookies.get("zmine_session")
            acc["sessionCookie"] = new_cookie
            print(f"  [{acc['user']['displayName']}] Re-login successful.")
            return True
        else:
            print(f"  [{acc['user']['displayName']}] Re-login failed: {rl.status_code} {rl.text}")
            return False
    return True


def run_account_cycle(acc: dict) -> None:
    name = acc.get("user", {}).get("displayName", "unknown")
    handle = acc.get("user", {}).get("handle", "")
    print(f"\n>>> Processing Account: {name} (Handle: {handle})")
    client = get_client_for_account(acc)
    try:
        # 1. Tor Exit IP check
        try:
            ip = client.get("https://api.ipify.org?format=json").json().get("ip")
            acc["torExitIp"] = ip
            print(f"  Tor Exit IP: {ip}")
        except Exception:
            pass

        # 2. Check session validity
        if not check_or_refresh_session(client, acc):
            return

        # 3. Mining status & activate
        client.headers.update({"Referer": "https://zmine.si/app/mine"})
        rm = client.get("https://zmine.si/api/v1/mining/overview").json()
        if not rm.get("sessionActive"):
            print("  Activating 24h mining session...")
            ra = client.post("https://zmine.si/api/v1/mining/activate").json()
            acc["miningStatus"] = "active"
            acc["sessionExpiresAt"] = ra.get("miner", {}).get("sessionExpiresAt")
            print("  Mining session activated!")
        else:
            acc["miningStatus"] = "active"
            acc["sessionExpiresAt"] = rm.get("sessionExpiresAt")
            print(f"  Mining already active until: {acc['sessionExpiresAt']}")

        # 4. Solve SI Daily Tasks
        client.headers.update({"Referer": "https://zmine.si/app/si"})
        while True:
            rt = client.get("https://zmine.si/api/v1/si/tasks/next")
            if rt.status_code != 200:
                print(f"  Failed to get next task: {rt.status_code}")
                break
            t_data = rt.json()
            stats = t_data.get("stats", {})
            correct = stats.get("correctToday", 0)
            cap = stats.get("cap", 12)
            print(f"  Tasks Progress: {correct}/{cap}")
            if correct >= cap:
                acc["tasksCompleted"] = f"{correct}/{cap}"
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
            ra = client.post(
                "https://zmine.si/api/v1/si/tasks/answer",
                json={"token": token, "answer": ans},
            )
            time.sleep(1.2)

        # 5. Final Overview Update
        client.headers.update({"Referer": "https://zmine.si/app"})
        rf = client.get("https://zmine.si/api/v1/mining/overview").json()
        hp = rf.get("hashpower", {}).get("totalMh", "0")
        acc["hashpower"] = f"{int(hp):,} Mh" if str(hp).isdigit() else f"{hp} Mh"
        print(
            f"  Done: Mining={acc['miningStatus']} | Hashpower={acc['hashpower']} | Tasks={acc.get('tasksCompleted')}"
        )
    finally:
        client.close()


def run_all() -> None:
    accounts = load_accounts()
    if not accounts:
        print(f"No accounts found in {ACCOUNTS_FILE}. Please run zmine_register.py first.")
        return
    print(f"Starting execution for {len(accounts)} accounts...")
    for acc in accounts:
        run_account_cycle(acc)
    save_accounts(accounts)
    print("\nAll accounts processed successfully!")


def show_status() -> None:
    accounts = load_accounts()
    print(f"Total Accounts: {len(accounts)}")
    total_balance = 0.0
    for i, a in enumerate(accounts, 1):
        u = a.get("user", {})
        dn = u.get("displayName")
        h = u.get("handle")
        tor_user = a.get("torUserId", "tor_default")
        proxy = f"socks5://{tor_user}:torpass123@{TOR_HOST}:{TOR_PORT}"
        headers = {"User-Agent": "Mozilla/5.0"}
        cookie = a.get("sessionCookie")
        avail_str = "0.0000"
        proj_day_str = "0.00"
        try:
            with httpx.Client(proxy=proxy, headers=headers, timeout=10.0) as client:
                if cookie:
                    client.cookies.set("zmine_session", cookie)
                rw = client.get("https://zmine.si/api/v1/wallet/balances").json()
                ro = client.get("https://zmine.si/api/v1/mining/overview").json()
                avail = int(rw.get("MINE", {}).get("available", 0)) / 1e8
                proj_day = int(ro.get("projectedPerDay", 0)) / 1e8
                avail_str = f"{avail:.4f}"
                proj_day_str = f"{proj_day:.2f}"
                total_balance += avail
        except Exception:
            pass

        print(
            f"[{i}] {dn} ({h}) | Saldo: {avail_str} MINE (Est: +{proj_day_str} MINE/hari) | "
            f"Mining: {a.get('miningStatus')} | Hash: {a.get('hashpower')} | "
            f"Tasks: {a.get('tasksCompleted')} | Tor: {a.get('torExitIp')}"
        )
    print(f"\nTotal Akumulasi MINE (Semua Akun): {total_balance:.4f} MINE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZMINE Multi-Account Automation Bot")
    parser.add_argument("action", choices=["run", "status"], default="run", nargs="?")
    args = parser.parse_args()
    if args.action == "status":
        show_status()
    else:
        run_all()
