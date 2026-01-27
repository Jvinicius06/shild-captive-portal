import json
import logging
import random
import string
import time
import urllib.request
import urllib.parse

from flask import Flask, jsonify, make_response, render_template, request

import config
import firewall

log = logging.getLogger(__name__)

app = Flask(__name__)

_redis = None

CHARS = string.ascii_uppercase + string.digits

SESSION_COOKIE = "wl_session"


def init(redis_client):
    global _redis
    _redis = redis_client


def _get_real_ip() -> str:
    if request.remote_addr in config.TRUSTED_PROXIES:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr


def _generate_code() -> str:
    return "".join(random.choices(CHARS, k=4))


def _check_rate_limit(ip: str) -> bool:
    """Return True if the IP is within rate limits (max 3 codes per 5 min)."""
    key = f"whitelist:ratelimit:{ip}"
    count = _redis.get(key)
    if count is not None and int(count) >= 3:
        return False
    pipe = _redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 300)
    pipe.execute()
    return True


def _verify_recaptcha(token: str) -> bool:
    """Verify a reCAPTCHA v3 response token with Google.

    Returns True if the token is valid, the action matches, and the
    score meets the configured threshold.
    """
    if not config.RECAPTCHA_SECRET_KEY:
        return True  # skip if not configured

    data = urllib.parse.urlencode({
        "secret": config.RECAPTCHA_SECRET_KEY,
        "response": token,
        "remoteip": _get_real_ip(),
    }).encode()

    req = urllib.request.Request(
        "https://www.google.com/recaptcha/api/siteverify",
        data=data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode())
    except Exception as e:
        log.error("reCAPTCHA verification failed: %s", e)
        return False

    if not result.get("success", False):
        log.warning("reCAPTCHA token invalid: %s", result.get("error-codes"))
        return False

    score = result.get("score", 0.0)
    action = result.get("action", "")

    if action != "renew_ip":
        log.warning("reCAPTCHA action mismatch: expected 'renew_ip', got '%s'", action)
        return False

    if score < config.RECAPTCHA_SCORE_THRESHOLD:
        log.warning("reCAPTCHA score too low: %.2f (threshold: %.2f)", score, config.RECAPTCHA_SCORE_THRESHOLD)
        return False

    log.info("reCAPTCHA passed: score=%.2f action=%s", score, action)
    return True


def _get_session_data() -> dict | None:
    """Return session data from cookie, or None if invalid/missing."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    raw = _redis.get(f"whitelist:session:{token}")
    if not raw:
        return None
    data = json.loads(raw)
    data["_token"] = token
    return data


def _update_session_ip(session_data: dict, new_ip: str) -> bool:
    """Update the session and firewall with a new IP."""
    token = session_data["_token"]
    old_ip = session_data.get("ip")

    # Remove old IP from firewall and active records
    if old_ip and old_ip != new_ip:
        firewall.remove_ip(old_ip)
        _redis.delete(f"whitelist:active:{old_ip}")

    # Add new IP
    if not firewall.add_ip(new_ip):
        return False

    # Update active record
    active_data = json.dumps({
        "discord_id": session_data["discord_id"],
        "discord_name": session_data["discord_name"],
        "timestamp": time.time(),
    })
    _redis.set(f"whitelist:active:{new_ip}", active_data)

    # Update session with new IP
    session_data["ip"] = new_ip
    updated = {k: v for k, v in session_data.items() if k != "_token"}
    _redis.setex(f"whitelist:session:{token}", config.SESSION_TTL, json.dumps(updated))

    return True


@app.route("/")
def index():
    ip = _get_real_ip()
    session = _get_session_data()

    # Check if there's a pending session cookie to set (after Discord validation)
    if firewall.is_whitelisted(ip):
        pending_token = _redis.get(f"whitelist:pending_session:{ip}")
        if pending_token:
            _redis.delete(f"whitelist:pending_session:{ip}")
            resp = make_response(
                render_template("index.html", code=None, already=True, ip=ip, ttl=0,
                                renew=False, recaptcha_key="")
            )
            resp.set_cookie(
                SESSION_COOKIE, pending_token,
                max_age=config.SESSION_TTL, httponly=True, samesite="Lax",
            )
            return resp

        # Also set cookie if session exists but cookie matches this IP
        return render_template("index.html", code=None, already=True, ip=ip, ttl=0,
                               renew=False, recaptcha_key="")

    # Session cookie exists but IP changed → show auto-renewal with reCAPTCHA
    if session and config.RECAPTCHA_SITE_KEY:
        return render_template("index.html", code=None, already=False, ip=ip, ttl=0,
                               renew=True, recaptcha_key=config.RECAPTCHA_SITE_KEY,
                               discord_name=session.get("discord_name", ""))

    # Normal flow: generate a new code
    if not _check_rate_limit(ip):
        return render_template("index.html", code=None, already=False, ip=ip, ttl=0,
                               error="rate_limit", renew=False, recaptcha_key=""), 429

    code = _generate_code()

    data = json.dumps({"ip": ip, "created_at": time.time()})
    _redis.setex(f"whitelist:code:{code}", config.CODE_TTL, data)

    log.info("Code %s generated for IP %s", code, ip)

    return render_template("index.html", code=code, already=False, ip=ip, ttl=config.CODE_TTL,
                           renew=False, recaptcha_key="")


@app.route("/renew", methods=["POST"])
def renew():
    ip = _get_real_ip()
    session = _get_session_data()

    if not session:
        return jsonify({"ok": False, "error": "Sessao invalida ou expirada. Use o fluxo normal com codigo."}), 401

    # Verify reCAPTCHA (accept token from JSON body or form data)
    if request.is_json:
        recaptcha_token = request.json.get("recaptcha_token", "")
    else:
        recaptcha_token = request.form.get("recaptcha_token", "")
    if not _verify_recaptcha(recaptcha_token):
        return jsonify({"ok": False, "error": "Verificacao reCAPTCHA falhou. Tente novamente."}), 403

    # Update IP
    success = _update_session_ip(session, ip)
    if not success:
        return jsonify({"ok": False, "error": "Falha ao atualizar IP. Contate um administrador."}), 500

    log.info("IP renewed: %s -> %s (discord: %s)", session.get("ip"), ip, session.get("discord_name"))

    # Refresh the session cookie TTL
    resp = make_response(jsonify({"ok": True}))
    resp.set_cookie(
        SESSION_COOKIE, session["_token"],
        max_age=config.SESSION_TTL, httponly=True, samesite="Lax",
    )
    return resp


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/status")
def status():
    ip = request.args.get("ip", _get_real_ip())
    whitelisted = firewall.is_whitelisted(ip)
    return jsonify({"ip": ip, "whitelisted": whitelisted})
