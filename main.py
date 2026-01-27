import logging
import threading

import redis as redis_lib

import bot
import config
import firewall
import web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def start_flask():
    web.app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=False,
        use_reloader=False,
    )


def main():
    log.info("Initializing whitelist portal...")

    r = redis_lib.Redis.from_url(config.REDIS_URL, decode_responses=True)
    r.ping()
    log.info("Redis connected")

    web.init(r)
    bot.init(r)
    firewall.init(r)

    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    log.info("Flask started on %s:%s", config.FLASK_HOST, config.FLASK_PORT)

    log.info("Starting Discord bot...")
    bot.client.run(config.DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
