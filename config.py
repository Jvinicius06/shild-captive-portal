import os
from dotenv import load_dotenv

load_dotenv()

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CODE_TTL = int(os.getenv("CODE_TTL", "300"))

IPSET_NAME = os.getenv("IPSET_NAME", "jogadores_permitidos")
PROTECTED_PORTS = os.getenv("PROTECTED_PORTS", "30120")

TRUSTED_PROXIES = [
    p.strip() for p in os.getenv("TRUSTED_PROXIES", "127.0.0.1").split(",") if p.strip()
]

PROXY_FIX_X_FOR = int(os.getenv("PROXY_FIX_X_FOR", "1"))

PORTAL_URL = os.getenv("PORTAL_URL", "http://localhost:5000")

LOG_WEBHOOK = os.getenv("LOG_WEBHOOK", "")

RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_SCORE_THRESHOLD = float(os.getenv("RECAPTCHA_SCORE_THRESHOLD", "0.5"))

SESSION_TTL = int(os.getenv("SESSION_TTL", str(30 * 24 * 3600)))  # 30 days
