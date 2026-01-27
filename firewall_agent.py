#!/usr/bin/env python3
"""
Firewall agent — runs natively on the host with root privileges.

Connects to Redis, restores active IPs into ipset on startup,
then consumes commands from the firewall queue to manage ipset
in real time.

Usage:
    sudo python3 firewall_agent.py
"""

import ipaddress
import json
import logging
import os
import subprocess
import sys
import signal
import time

import redis as redis_lib
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("firewall_agent")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
IPSET_NAME = os.getenv("IPSET_NAME", "jogadores_permitidos")
QUEUE_KEY = "whitelist:firewall_queue"
ACTIVE_PREFIX = "whitelist:active:"

_running = True


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)


def _validate_ip(ip: str) -> str:
    return str(ipaddress.ip_address(ip))


def setup_ipset() -> None:
    """Create the ipset if it does not already exist."""
    result = _run(["ipset", "create", IPSET_NAME, "hash:ip", "-exist"])
    if result.returncode != 0:
        log.error("ipset create failed: %s", result.stderr.strip())
        sys.exit(1)
    log.info("ipset '%s' ready", IPSET_NAME)


def restore_ips(r: redis_lib.Redis) -> int:
    """Restore all active IPs from Redis into ipset."""
    count = 0
    for key in r.scan_iter(f"{ACTIVE_PREFIX}*"):
        ip = key.removeprefix(ACTIVE_PREFIX)
        try:
            ip = _validate_ip(ip)
        except ValueError:
            log.warning("Skipping invalid IP in Redis: %s", ip)
            continue
        result = _run(["ipset", "add", IPSET_NAME, ip, "-exist"])
        if result.returncode == 0:
            count += 1
        else:
            log.error("Failed to restore IP %s: %s", ip, result.stderr.strip())
    return count


def handle_command(cmd: dict) -> None:
    """Execute a single firewall command from the queue."""
    action = cmd.get("action")

    if action == "add":
        ip = _validate_ip(cmd["ip"])
        result = _run(["ipset", "add", IPSET_NAME, ip, "-exist"])
        if result.returncode != 0:
            log.error("ipset add %s failed: %s", ip, result.stderr.strip())
        else:
            log.info("IP added to ipset: %s", ip)

    elif action == "remove":
        ip = _validate_ip(cmd["ip"])
        result = _run(["ipset", "del", IPSET_NAME, ip, "-exist"])
        if result.returncode != 0:
            log.error("ipset del %s failed: %s", ip, result.stderr.strip())
        else:
            log.info("IP removed from ipset: %s", ip)

    elif action == "flush":
        result = _run(["ipset", "flush", IPSET_NAME])
        if result.returncode != 0:
            log.error("ipset flush failed: %s", result.stderr.strip())
        else:
            log.info("ipset flushed")

    else:
        log.warning("Unknown command action: %s", action)


def _shutdown(signum, frame):
    global _running
    log.info("Received signal %s, shutting down...", signum)
    _running = False


def main():
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("Firewall agent starting...")
    log.info("Redis: %s | ipset: %s", REDIS_URL, IPSET_NAME)

    r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    log.info("Redis connected")

    setup_ipset()

    restored = restore_ips(r)
    log.info("Restored %d IPs from Redis into ipset", restored)

    log.info("Listening for firewall commands on '%s'...", QUEUE_KEY)

    while _running:
        try:
            result = r.blpop(QUEUE_KEY, timeout=5)
            if result is None:
                continue
            _, raw = result
            cmd = json.loads(raw)
            handle_command(cmd)
        except redis_lib.ConnectionError:
            log.error("Redis connection lost, reconnecting in 5s...")
            time.sleep(5)
            try:
                r.ping()
            except Exception:
                r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
        except ValueError as e:
            log.error("Invalid command data: %s", e)
        except Exception as e:
            log.error("Unexpected error: %s", e)
            time.sleep(1)

    log.info("Firewall agent stopped")


if __name__ == "__main__":
    main()
