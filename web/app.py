"""
MOFIX Countdown Bot - Web Dashboard & Public Site
"""
import datetime as dt
import shutil

from flask import (Flask, render_template, request, redirect, url_for,
                    flash, jsonify, send_file, abort)
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                          login_required)

from common.config import config
from common.db import init_db, get_session
from common.models import Admin, Countdown, BotStatus, BOT_STATUS_SINGLETON_ID
from common.utils import (verify_password, slugify, local_to_utc, utc_to_local,
                           remaining_parts)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY


@app.template_filter("to_local")
def _to_local_filter(value, tz_name):
    """Render a naive-UTC datetime column as local time in `tz_name`.

    Used anywhere the template needs to show the countdown's target time
    the way the admin originally entered it (dashboard table, edit form),
    rather than the raw UTC value stored in the database.
    """
    if value is None:
        return ""
    try:
        return utc_to_local(value, tz_name or config.DEFAULT_TIMEZONE)
    except Exception:
        return value

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class AdminUser(UserMixin):
    def __init__(self, admin: Admin):
        self.id = admin.id
        self.username = admin.username


@login_manager.user_loader
def load_user(user_id):
    with get_session() as db:
        admin = db.query(Admin).filter_by(id=int(user_id)).first()
        return AdminUser(admin) if admin else None


# --------------------------------------------------------------------------
# Public site
# --------------------------------------------------------------------------

@app.route("/")
def public_home():
    with get_session() as db:
        countdowns = (
            db.query(Countdown)
            .filter(Countdown.status.in_(["active", "completed"]))
            .order_by(Countdown.target_datetime_utc.asc())
            .all()
        )
        db.expunge_all()
    return render_template("public.html", countdowns=countdowns)


@app.route("/countdown/<slug>")
def public_countdown(slug):
    with get_session() as db:
        countdown = db.query(Countdown).filter_by(slug=slug).first()
        if not countdown:
            abort(404)
        db.expunge(countdown)
    return render_template("public_single.html", countdown=countdown)


@app.route("/api/countdowns")
def api_countdowns():
    """JSON feed the front-end JS polls to keep timers accurate without a refresh."""
    with get_session() as db:
        countdowns = (
            db.query(Countdown)
            .filter(Countdown.status.in_(["active", "completed"]))
            .all()
        )
        data = []
        now = dt.datetime.utcnow()
        for c in countdowns:
            days, hours, minutes, seconds, total = remaining_parts(c.target_datetime_utc, now)
            data.append({
                "id": c.id,
                "slug": c.slug,
                "name": c.name,
                "title_line": c.title_line,
                "subtitle_line": c.subtitle_line,
                "live_message": c.live_message,
                "status": c.status,
                "target_datetime_utc": c.target_datetime_utc.isoformat() + "Z",
                "days": days, "hours": hours, "minutes": minutes, "seconds": seconds,
                "total_seconds": total,
            })
    return jsonify(data)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_session() as db:
            admin = db.query(Admin).filter_by(username=username).first()
            if admin and verify_password(password, admin.password_hash):
                login_user(AdminUser(admin))
                flash("Welcome back!", "success")
                return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

@app.route("/admin")
@login_required
def dashboard():
    with get_session() as db:
        countdowns = db.query(Countdown).order_by(Countdown.created_at.desc()).all()
        # Fixed singleton id: guarantees we're reading the exact same row
        # the bot process heartbeats into (see common/models.py).
        status = db.get(BotStatus, BOT_STATUS_SINGLETON_ID)
        db.expunge_all()

    is_online = False
    if status and status.last_heartbeat:
        age = (dt.datetime.utcnow() - status.last_heartbeat).total_seconds()
        is_online = age <= config.HEARTBEAT_STALE_SECONDS

    return render_template(
        "dashboard.html",
        countdowns=countdowns,
        bot_online=is_online,
        bot_status=status,
    )


@app.route("/admin/countdown/new", methods=["GET", "POST"])
@login_required
def countdown_new():
    if request.method == "POST":
        _save_countdown_from_form(None)
        flash("Countdown created.", "success")
        return redirect(url_for("dashboard"))
    return render_template("countdown_form.html", countdown=None, timezones=_common_timezones())


@app.route("/admin/countdown/<int:countdown_id>/edit", methods=["GET", "POST"])
@login_required
def countdown_edit(countdown_id):
    with get_session() as db:
        countdown = db.query(Countdown).filter_by(id=countdown_id).first()
        if not countdown:
            abort(404)
        if request.method == "POST":
            _save_countdown_from_form(countdown_id)
            flash("Countdown updated.", "success")
            return redirect(url_for("dashboard"))
        db.expunge(countdown)
    return render_template("countdown_form.html", countdown=countdown, timezones=_common_timezones())


@app.route("/admin/countdown/<int:countdown_id>/delete", methods=["POST"])
@login_required
def countdown_delete(countdown_id):
    with get_session() as db:
        countdown = db.query(Countdown).filter_by(id=countdown_id).first()
        if countdown:
            db.delete(countdown)
    flash("Countdown deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/countdown/<int:countdown_id>/start", methods=["POST"])
@login_required
def countdown_start(countdown_id):
    with get_session() as db:
        db.query(Countdown).filter_by(id=countdown_id).update(
            {"status": "active"}, synchronize_session=False
        )
    flash("Countdown started. The bot will post/update it within a minute.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/countdown/<int:countdown_id>/stop", methods=["POST"])
@login_required
def countdown_stop(countdown_id):
    with get_session() as db:
        db.query(Countdown).filter_by(id=countdown_id).update(
            {"status": "stopped"}, synchronize_session=False
        )
    flash("Countdown stopped.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/bot/restart", methods=["POST"])
@login_required
def bot_restart():
    with get_session() as db:
        status = db.get(BotStatus, BOT_STATUS_SINGLETON_ID)
        if not status:
            status = BotStatus(id=BOT_STATUS_SINGLETON_ID)
            db.add(status)
        status.restart_requested = True
    flash("Restart requested. The bot process will exit and your process "
          "manager (Docker/Railway/Render/systemd) will bring it back up.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/backup", methods=["GET"])
@login_required
def backup_db():
    ts = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    dest = config.BACKUP_DIR / f"mofix-backup-{ts}.db"
    shutil.copy(config.DATABASE_PATH, dest)
    return send_file(dest, as_attachment=True, download_name=dest.name)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _common_timezones():
    return [
        "Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Asia/Tokyo",
        "Europe/London", "Europe/Berlin", "America/New_York",
        "America/Los_Angeles", "America/Chicago", "Australia/Sydney", "UTC",
    ]


def _save_countdown_from_form(countdown_id):
    form = request.form
    tz_name = form.get("timezone", config.DEFAULT_TIMEZONE)
    naive_local = dt.datetime.strptime(form.get("target_datetime"), "%Y-%m-%dT%H:%M")
    target_utc = local_to_utc(naive_local, tz_name)

    with get_session() as db:
        if countdown_id:
            countdown = db.query(Countdown).filter_by(id=countdown_id).first()
        else:
            countdown = Countdown()
            db.add(countdown)

        countdown.name = form.get("name", "Untitled Countdown").strip()
        countdown.slug = slugify(form.get("slug") or countdown.name)
        countdown.title_line = form.get("title_line") or "MOFIX AUTH TOOL"
        countdown.subtitle_line = form.get("subtitle_line") or "Release Countdown"
        countdown.live_message = form.get("live_message") or "MOFIX AUTH TOOL IS NOW LIVE!"
        countdown.announcement_text = form.get("announcement_text") or "The wait is over! 🎉"
        countdown.target_datetime_utc = target_utc
        countdown.timezone = tz_name
        countdown.chat_id = form.get("chat_id") or None


def create_app():
    init_db()
    return app


if __name__ == "__main__":
    create_app()
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=config.DEBUG)
