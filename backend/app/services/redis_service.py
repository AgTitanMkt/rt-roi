import json
import logging
import os
from decimal import Decimal

import redis

from ..core.redis import redis_client
from .metrics_service import get_summary, get_metrics_by_hour

logger = logging.getLogger(__name__)
CACHE_TTL_SECONDS = int(os.getenv("REDIS_CACHE_TTL_SECONDS", "300"))


def _normalize_source(source):
    if source is None:
        return None
    normalized = source.strip()
    if not normalized:
        return None
    if normalized.lower() in {"all", "todos", "todos os squads"}:
        return None
    return normalized


def _to_jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _is_summary_payload(payload):
    return isinstance(payload, dict) and {"today", "yesterday", "comparison"}.issubset(payload.keys())


def _is_hourly_payload(payload):
    if not isinstance(payload, list):
        return False
    required_keys = {"slot", "day", "hour", "cost", "profit", "revenue", "roi"}
    return all(isinstance(item, dict) and required_keys.issubset(item.keys()) for item in payload)


def _hourly_to_list(rows):
    result = []
    for row in rows or []:
        mapping = row._mapping if hasattr(row, "_mapping") else row
        result.append(
            {
                "squad": str(mapping.get("squad") or ""),
                "slot": str(mapping.get("slot") or ""),
                "day": str(mapping.get("day") or ""),
                "hour": str(mapping.get("hour") or ""),
                "cost": float(mapping.get("cost") or 0),
                "profit": float(mapping.get("profit") or 0),
                "revenue": float(mapping.get("revenue") or 0),
                "roi": float(mapping.get("roi") or 0),
            }
        )
    return result


def _cache_get(cache_key):
    try:
        cached = redis_client.get(cache_key)
        return json.loads(cached) if cached else None
    except (redis.RedisError, json.JSONDecodeError) as exc:
        logger.warning("Redis get falhou para %s: %s", cache_key, exc)
        return None


def _cache_set(cache_key, data, ttl=CACHE_TTL_SECONDS):
    try:
        redis_client.setex(cache_key, ttl, json.dumps(data))
    except redis.RedisError as exc:
        logger.warning("Redis set falhou para %s: %s", cache_key, exc)


def invalidate_metrics_cache():
    deleted = 0
    for pattern in ("summary:*", "hourly:*"):
        try:
            keys = list(redis_client.scan_iter(match=pattern, count=200))
            if keys:
                deleted += redis_client.delete(*keys)
        except redis.RedisError as exc:
            logger.warning("Redis invalidação falhou para %s: %s", pattern, exc)
    return deleted


def get_summary_cached(db, source=None):
    source = _normalize_source(source)
    cache_key = f"summary:{source or 'all'}"

    cached = _cache_get(cache_key)
    if _is_summary_payload(cached):
        return cached

    data = get_summary(db, source)
    payload = _to_jsonable(data)
    _cache_set(cache_key, payload)
    return payload


def get_hourly_cached(db, source=None):
    source = _normalize_source(source)
    cache_key = f"hourly:v2:{source or 'all'}"

    cached = _cache_get(cache_key)
    if _is_hourly_payload(cached):
        return cached

    data = get_metrics_by_hour(db, source)
    payload = _hourly_to_list(data)
    _cache_set(cache_key, payload)
    return payload
