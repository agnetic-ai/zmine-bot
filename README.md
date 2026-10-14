# ZMINE Automation Bot

Bot otomasi multi-account untuk platform penambangan token ZMINE ($MINE on Zcash - [zmine.si](https://zmine.si)). Dilengkapi dengan modul pendaftaran otomatis, isolasi IP per akun via Tor SOCKS5, aktivasi mining harian 24 jam, dan dual-engine solver untuk menyelesaikan 12 tugas kuis harian (SI Tasks).

---

## Fitur Utama

- **Multi-Account Management:** Mengelola puluhan akun sekaligus secara terstruktur melalui database `accounts.json`.
- **Tor Stream Isolation (IP Rotation):** Menggunakan fitur sirkuit SOCKS5 Tor (`socks5://tor_user:pass@127.0.0.1:9050`) sehingga setiap akun secara otomatis mendaftar dan beroperasi menggunakan Exit IP Tor yang berbeda tanpa perlu me-restart service Tor.
- **Dedicated Auto-Registrar (`zmine_register.py`):**
  - Generator nama natural Indonesia (bukan nama generik / bot-like).
  - Pendaftaran otomatis dengan target kode referral tertentu.
  - Langsung mengaktifkan sesi penambangan pertama kali dan menyelesaikan 12 tugas harian.
- **Daily Mining Automation (`zmine_bot.py`):**
  - Siklus 24 jam penambangan gratis.
  - Menjaga streak harian (+2% hashpower per hari, maksimal +20%).
  - Pengecekan sesi otomatis; jika cookie kedaluwarsa, bot otomatis melakukan re-login menggunakan `loginKey`.
- **Dual-Engine SI Tasks Solver (12/12 Task Harian):**
  - **Lapis 1 (Regex & Math Rules):** Menyelesaikan secara instan tanpa biaya token untuk soal-soal berpola (perhitungan blok per hari, epoch per durasi, konversi ZEC ke zatoshi, persentase nilai, klaim aritmatika, dll).
  - **Lapis 2 (Local / Remote AI Fallback):** Mendukung OpenAI-compatible API (seperti 9Router, Ollama, OpenRouter, atau OpenAI) untuk menjawab soal logika, teks, atau trivia crypto yang tidak berpola.
  - **Proteksi Anti-TooFast:** Menyematkan delay terukur 3.6 detik sebelum submit jawaban untuk memenuhi validasi timestamp backend ZMINE.
- **Pencadangan Kredensial:** Otomatis mengekspor `credentials.txt` dan mendukung pengiriman file dokumen cadangan langsung ke Telegram.

---

## Struktur Direktori

```text
zmine-bot/
├── zmine_bot.py           # Runner harian: mining cycle, task solver, status
├── zmine_register.py      # Tool pendaftaran akun baru multi-account via Tor
├── solver.py              # Dual-engine solver (Regex rules + AI fallback)
├── accounts.example.json  # Template format data akun
├── .env.example           # Template variabel lingkungan
├── requirements.txt       # Dependensi Python
└── README.md              # Dokumentasi lengkap
```

---

## Prasyarat Sistem

1. **Sistem Operasi:** Linux (Ubuntu/Debian direkomendasikan) atau macOS.
2. **Python:** Versi 3.10 atau lebih baru.
3. **Tor Daemon:** Berstatus aktif pada port lokal `9050`.
   ```bash
   sudo apt update && sudo apt install -y tor
   sudo systemctl enable --now tor
   ```

---

## Instalasi

1. **Clone Repository:**
   ```bash
   git clone https://github.com/agnetic-ai/zmine-bot.git
   cd zmine-bot
   ```

2. **Pasang Dependensi:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Atau gunakan virtual environment `python3 -m venv .venv && source .venv/bin/activate`)*

3. **Konfigurasi Environment:**
   Salin file konfigurasi contoh:
   ```bash
   cp .env.example .env
   ```
   Sesuaikan parameter di dalam `.env`:
   ```ini
   # Direktori penyimpanan data (opsional, default: folder script)
   # ZMINE_DATA_DIR=/opt/zmine

   # Konfigurasi Tor SOCKS5
   TOR_PROXY_HOST=127.0.0.1
   TOR_PROXY_PORT=9050

   # Kode Referral Default untuk Pendaftaran
   ZMINE_DEFAULT_REF=4VN2PNKK

   # AI Solver (Opsional - fallback kuis logika)
   ZMINE_AI_URL=http://127.0.0.1:20128/v1/chat/completions
   ZMINE_AI_KEY=
   ZMINE_AI_MODEL=ag/gemini-3.8-flash-low

   # Telegram Notification (Opsional - pengiriman file kredensial)
   TELEGRAM_BOT_TOKEN=
   TELEGRAM_CHAT_ID=
   ```

---

## Panduan Penggunaan

### 1. Pendaftaran Akun Baru (`zmine_register.py`)

Gunakan script ini khusus untuk membuat akun baru:

- **Mendaftar 1 akun baru:**
  ```bash
  python3 zmine_register.py --count 1
  ```
- **Mendaftar beberapa akun sekaligus (misal 5 akun):**
  ```bash
  python3 zmine_register.py --count 5
  ```
- **Menggunakan kode referral khusus:**
  ```bash
  python3 zmine_register.py --count 3 --ref KODE_REFERRAL
  ```
- **Hanya mendaftar dan start mining (lewati task harian):**
  ```bash
  python3 zmine_register.py --count 5 --skip-tasks
  ```

Setiap akun yang didaftarkan akan otomatis:
1. Mendapatkan nama natural unik.
2. Didaftarkan melalui exit IP Tor yang terisolasi.
3. Mengaktifkan mining sesi pertama.
4. Menyelesaikan 12 tugas harian (+60,000 Mh).
5. Disimpan ke dalam `accounts.json` dan `credentials.txt`.

### 2. Menjalankan Siklus Harian (`zmine_bot.py`)

Untuk merawat akun yang sudah terdaftar (mengecek sesi, aktivasi ulang mining, dan menyelesaikan kuis harian):

- **Jalankan siklus semua akun:**
  ```bash
  python3 zmine_bot.py run
  ```
- **Cek ringkasan status semua akun:**
  ```bash
  python3 zmine_bot.py status
  ```

Output status akan menampilkan informasi:
```text
Total Accounts: 4
[1] nisa_pratama (HANDLE1) | Mining: active | Hashpower: 62,220 Mh | Tasks: 12/12 | Tor IP: 185.220.101.188
[2] anis_savitri (HANDLE2) | Mining: active | Hashpower: 62,220 Mh | Tasks: 12/12 | Tor IP: 192.42.116.95
[3] yani_lestari (HANDLE3) | Mining: active | Hashpower: 62,220 Mh | Tasks: 12/12 | Tor IP: 109.70.100.4
[4] ayu_gunawan (HANDLE4) | Mining: active | Hashpower: 62,220 Mh | Tasks: 12/12 | Tor IP: 185.39.207.83
```

---

## Otomasi Penjadwalan (Cronjob VPS)

Agar bot berjalan otomatis setiap 24 jam sekali di VPS, pasang jadwal cronjob:

```bash
crontab -e
```

Tambahkan baris berikut (contoh: dieksekusi setiap hari jam 03:30 pagi):
```bash
30 3 * * * cd /opt/zmine && /usr/bin/python3 zmine_bot.py run >> /opt/zmine/bot.log 2>&1
```

---

## Format Data Akun (`accounts.json`)

Data akun disimpan dalam format JSON array terenkapsulasi:

```json
[
  {
    "user": {
      "id": "72bfda4e-81e2-4c2b-a5c4-cb2652fbb6b1",
      "handle": "EXAMPLE1",
      "role": "user",
      "displayName": "ayu_gunawan"
    },
    "loginKey": "LK-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
    "recoveryPhrase": "word1 word2 word3 ... word24",
    "referralCodeUsed": "4VN2PNKK",
    "sessionCookie": "zmine_session=...",
    "torUserId": "tor_acc_1791950852_384",
    "torExitIp": "185.220.101.188",
    "createdAt": "2026-10-14T03:34:00.000Z",
    "miningStatus": "active",
    "sessionExpiresAt": "2026-10-15T03:34:00.000Z",
    "hashpower": "62,220 Mh",
    "tasksCompleted": "12/12"
  }
]
```

---

## Keamanan & Praktik Terbaik

1. **Jaga Kerahasiaan Kredensial:** Jangan pernah mengunggah file `accounts.json` atau `credentials.txt` ke repository publik. File-file tersebut sudah dimasukkan ke `.gitignore`.
2. **Kredensial SOCKS5 Tor:** Fitur isolasi sirkuit otomatis memetakan nama user proxy menjadi sirkuit unik di Tor daemon. Tidak diperlukan password autentikasi nyata pada Tor lokal secara default.
3. **Delay Proteksi:** Jangan mempercepat waktu tunggu antar soal di bawah 3.5 detik karena backend ZMINE memvalidasi timestamp generasi token untuk mendeteksi otomasi.

---

## Lisensi

Proyek ini dirilis di bawah lisensi MIT. Gunakan untuk kebutuhan edukasi dan pengujian sistem.
