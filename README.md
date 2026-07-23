# 🚀 MOFIX Countdown Bot

A production-ready Telegram countdown system: a 24/7 bot that keeps a single
pinned message updated every minute, a secure admin dashboard to manage
everything without touching code, and a premium dark/glassmorphism public
website with a live, self-updating countdown.

```
🚀 MOFIX AUTH TOOL
⏳ Release Countdown
02 Days  14 Hours  32 Minutes
```

---

## ✨ Features

**Telegram bot**
- Built with `aiogram` 3.x, runs 24/7 on any host.
- Edits one pinned message every minute — never spams the chat.
- Automatically posts and pins the message the first time a countdown starts.
- On zero: stops, edits the message to the "live" announcement, and posts a
  fresh announcement message.
- Supports **multiple simultaneous countdowns**, each with its own chat.
- Full timezone support (defaults to `Asia/Kolkata`).
- All data in SQLite — no external database required.

**Admin dashboard** (Flask, password-protected)
- Create / edit / delete countdowns.
- Set release date, time and timezone with a normal date picker.
- Start / stop any countdown.
- See at a glance whether a message is pinned.
- Live bot status (Online / Offline) from a heartbeat check.
- One-click "Restart bot" (safe under Docker/Railway/Render process
  supervision — see [Restarting the bot](#restarting-the-bot)).
- One-click database backup download.

**Public website**
- Dark, premium, glassmorphism "launch console" design with blue/cyan glow.
- Days / Hours / Minutes / Seconds, ticking every second client-side.
- Re-syncs with the server every 20 seconds — always accurate, never drifts,
  reacts to admin edits without a page refresh.
- Shows **🎉 Released Successfully** automatically at zero.
- Fully responsive, fast, semantic HTML with SEO meta tags.

---

## 📁 Folder structure

```
mofix-countdown-bot/
├── bot/
│   ├── bot.py            # aiogram bot + countdown loop
│   └── repository.py     # DB access helpers used by the bot
├── web/
│   ├── app.py             # Flask app: public site + admin dashboard
│   ├── templates/         # Jinja2 templates
│   └── static/
│       ├── css/style.css  # design system (site + admin)
│       └── js/countdown.js
├── common/
│   ├── config.py           # env-based configuration
│   ├── db.py                # SQLAlchemy engine/session + init
│   ├── models.py            # Admin, Countdown, BotStatus
│   └── utils.py             # password hashing, timezones, formatting
├── data/                    # SQLite database lives here (auto-created)
├── backups/                 # DB backups land here
├── run_bot.py               # entry point: python run_bot.py
├── run_web.py                # entry point: python run_web.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Procfile                  # for Railway/Render/Heroku-style deploys
├── .env.example
└── README.md
```

---

## 🔧 Requirements

- Python 3.10+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- The bot must be an **admin** in any chat/channel it posts and pins in

---

## 🖥️ Local installation

```bash
git clone <your-repo-url> mofix-countdown-bot
cd mofix-countdown-bot

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env: set BOT_TOKEN, SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD
```

Run the two processes in separate terminals:

```bash
# Terminal 1 — web dashboard + public site
python run_web.py

# Terminal 2 — Telegram bot
python run_bot.py
```

- Dashboard: http://localhost:5000/admin/login
- Public site: http://localhost:5000/

On first run, `init_db()` automatically creates `data/mofix.db` and seeds the
admin account from `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env`.

> ⚠️ Change `ADMIN_PASSWORD` and `SECRET_KEY` before deploying anywhere public.

---

## 📲 Creating your first countdown

1. Log in to `/admin/login`.
2. Click **+ New Countdown**.
3. Fill in the name, target date/time, timezone, and the Telegram
   **Chat ID** (a channel/group where the bot is an admin — e.g.
   `-1001234567890` or `@yourchannel`).
4. Save, then click **Start** on the dashboard.
5. Within a minute, the bot posts and pins the countdown message and starts
   editing it every minute automatically.

To find a channel's chat ID, add [@userinfobot](https://t.me/userinfobot) or
forward a message from the channel to [@JsonDumpBot](https://t.me/JsonDumpBot).

---

## 🔁 Restarting the bot

The dashboard's **Restart Bot** button sets a flag in the database. The bot
process checks this flag every cycle and exits cleanly (`sys.exit(0)`) when
it's set — it does **not** kill the process directly. For this to actually
restart the bot, run it under a supervisor that restarts on exit:

- **Docker / docker-compose**: already configured with `restart: unless-stopped`.
- **Railway / Render**: services restart automatically on process exit.
- **VPS**: use `systemd` (see below) or `pm2`/`supervisord`.

---

## ☁️ Deployment

### Docker (recommended)

```bash
cp .env.example .env   # fill in your values
docker compose up -d --build
```

This starts two containers — `mofix-web` and `mofix-bot` — sharing the same
SQLite database via a named volume, both auto-restarting.

### Railway / Render

1. Push this repo to GitHub.
2. Create **two services** from the same repo:
   - **Web service** — start command: `gunicorn -w 2 -b 0.0.0.0:$PORT run_web:app`
   - **Worker/Background service** — start command: `python run_bot.py`
3. Add the environment variables from `.env.example` to both services.
4. Both platforms auto-detect the `Procfile` if you prefer that instead of
   manually setting start commands.
5. ⚠️ **Critical step — shared database.** Each Railway/Render service is
   its own container with its own private, ephemeral disk. If the Web
   service and the Bot service each get their own disk, they end up with
   two *different* SQLite files: countdowns created (or started) in the
   admin never appear on the public site's queries against the bot's copy,
   and the bot's heartbeat never reaches the copy the dashboard reads —
   which is exactly the "Bot Status: Offline" / "No countdowns are
   running" symptom.

   To fix this, both services **must** mount the same persistent Volume at
   the same path:
   - In Railway: create one Volume, then attach that *same* Volume to both
     the web service and the bot service, mounted at (for example)
     `/app/data`.
   - Set `DATABASE_URL` (or `DATABASE_FILE`) identically on both services
     so they resolve to the same file inside that shared mount — e.g.
     `DATABASE_URL=sqlite:////app/data/mofix.db`.
   - On startup both processes log the resolved database path
     (`Using database: ...`) — check both services' logs and confirm they
     print the exact same path.

### VPS (systemd)

```ini
# /etc/systemd/system/mofix-bot.service
[Unit]
Description=MOFIX Countdown Bot
After=network.target

[Service]
WorkingDirectory=/opt/mofix-countdown-bot
ExecStart=/opt/mofix-countdown-bot/.venv/bin/python run_bot.py
Restart=always
EnvironmentFile=/opt/mofix-countdown-bot/.env

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/mofix-web.service
[Unit]
Description=MOFIX Web Dashboard
After=network.target

[Service]
WorkingDirectory=/opt/mofix-countdown-bot
ExecStart=/opt/mofix-countdown-bot/.venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 run_web:app
Restart=always
EnvironmentFile=/opt/mofix-countdown-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mofix-bot mofix-web
```

Put Nginx in front of port 5000 for TLS/HTTPS in production.

---

## 🔐 Security notes

- Passwords are hashed with Werkzeug's `generate_password_hash`.
- Sessions use Flask-Login with a secret key you control (`SECRET_KEY`).
- Never commit your `.env` file — it's already in `.gitignore`.
- Rotate `ADMIN_PASSWORD` and `SECRET_KEY` before going to production.

---

## 🧩 Tech stack

| Layer          | Choice                     |
|----------------|-----------------------------|
| Bot framework  | aiogram 3.x                |
| Web framework  | Flask + Flask-Login        |
| Database       | SQLite via SQLAlchemy 2.x  |
| Frontend       | Vanilla HTML/CSS/JS (no build step) |
| Hosting        | Docker / Railway / Render / any VPS |

---

## 📄 License

Provided as-is for the MOFIX project. Adapt freely for your own deployment.
