import ipaddress
import json
import logging

log = logging.getLogger(__name__)

_redis = None

QUEUE_KEY = "whitelist:firewall_queue"
ACTIVE_PREFIX = "whitelist:active:"


def init(redis_client) -> None:
    """Store the Redis client for later use."""
    global _redis
    _redis = redis_client
    log.info("Firewall module initialized (Redis proxy mode)")


def _validate_ip(ip: str) -> str:
    """Validate and return the normalized IP string. Raises ValueError on bad input."""
    return str(ipaddress.ip_address(ip))


def _enqueue(command: dict) -> bool:
    """Push a command onto the firewall queue for the host agent."""
    try:
        _redis.rpush(QUEUE_KEY, json.dumps(command))
        return True
    except Exception as e:
        log.error("Failed to enqueue firewall command: %s", e)
        return False


def add_ip(ip: str) -> bool:
    ip = _validate_ip(ip)
    ok = _enqueue({"action": "add", "ip": ip})
    if ok:
        log.info("Enqueued IP add: %s", ip)
    return ok


def remove_ip(ip: str) -> bool:
    ip = _validate_ip(ip)
    ok = _enqueue({"action": "remove", "ip": ip})
    if ok:
        log.info("Enqueued IP remove: %s", ip)
    return ok


def flush() -> bool:
    ok = _enqueue({"action": "flush"})
    if ok:
        log.info("Enqueued ipset flush")
    return ok


def is_whitelisted(ip: str) -> bool:
    ip = _validate_ip(ip)
    return _redis.exists(f"{ACTIVE_PREFIX}{ip}") == 1


def list_ips() -> list[str]:
    ips = []
    for key in _redis.scan_iter(f"{ACTIVE_PREFIX}*"):
        ip = key.removeprefix(ACTIVE_PREFIX)
        ips.append(ip)
    return ips
