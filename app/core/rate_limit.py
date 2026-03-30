from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import FastAPI, Request, status
from starlette.responses import Response

from app.core.config import Settings
from app.core.errors import build_error_response

RATE_LIMIT_EXCEEDED_MESSAGE = "Rate limit exceeded. Try again later."


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    name: str
    method: str
    path: str
    limit: int
    window_seconds: int


@dataclass(slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


@dataclass(slots=True)
class WindowCounter:
    window_started_at: float
    count: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._counters: dict[tuple[str, str], WindowCounter] = {}
        self._lock = Lock()

    def evaluate(self, *, rule: RateLimitRule, client_id: str) -> RateLimitDecision:
        now = monotonic()
        key = (rule.name, client_id)

        with self._lock:
            counter = self._counters.get(key)
            if counter is None or now - counter.window_started_at >= rule.window_seconds:
                counter = WindowCounter(window_started_at=now, count=0)
                self._counters[key] = counter

            if counter.count >= rule.limit:
                return RateLimitDecision(
                    allowed=False,
                    limit=rule.limit,
                    remaining=0,
                    retry_after_seconds=self._build_retry_after(
                        now=now,
                        window_started_at=counter.window_started_at,
                        window_seconds=rule.window_seconds,
                    ),
                )

            counter.count += 1
            remaining = max(rule.limit - counter.count, 0)
            self._prune_expired_counters(now)
            return RateLimitDecision(
                allowed=True,
                limit=rule.limit,
                remaining=remaining,
                retry_after_seconds=self._build_retry_after(
                    now=now,
                    window_started_at=counter.window_started_at,
                    window_seconds=rule.window_seconds,
                ),
            )

    def _prune_expired_counters(self, now: float) -> None:
        if len(self._counters) < 1024:
            return

        expired_keys = [
            key
            for key, counter in self._counters.items()
            if now - counter.window_started_at >= 300
        ]
        for key in expired_keys:
            self._counters.pop(key, None)

    @staticmethod
    def _build_retry_after(
        *,
        now: float,
        window_started_at: float,
        window_seconds: int,
    ) -> int:
        elapsed = now - window_started_at
        remaining = max(window_seconds - elapsed, 0)
        return max(1, ceil(remaining))


def install_rate_limit_middleware(app: FastAPI, settings: Settings) -> None:
    rules = _build_rules(settings)
    if not rules:
        return

    limiter = InMemoryRateLimiter()
    rule_lookup = {(rule.method, rule.path): rule for rule in rules}

    @app.middleware("http")
    async def rate_limit_requests(request: Request, call_next) -> Response:
        rule = rule_lookup.get((request.method.upper(), request.url.path))
        if rule is None:
            return await call_next(request)

        client_id = request.client.host if request.client is not None else "unknown"
        decision = limiter.evaluate(rule=rule, client_id=client_id)
        headers = {
            "Retry-After": str(decision.retry_after_seconds),
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": str(decision.remaining),
        }
        if not decision.allowed:
            return build_error_response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                message=RATE_LIMIT_EXCEEDED_MESSAGE,
                headers=headers,
            )

        response = await call_next(request)
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value
        return response


def _build_rules(settings: Settings) -> list[RateLimitRule]:
    candidates = [
        (
            "auth_login",
            "POST",
            f"{settings.api_v1_prefix}/auth/login",
            settings.login_rate_limit_requests,
        ),
        (
            "auth_register",
            "POST",
            f"{settings.api_v1_prefix}/auth/register",
            settings.register_rate_limit_requests,
        ),
        (
            "auth_refresh",
            "POST",
            f"{settings.api_v1_prefix}/auth/refresh",
            settings.refresh_rate_limit_requests,
        ),
    ]

    return [
        RateLimitRule(
            name=name,
            method=method,
            path=path,
            limit=limit,
            window_seconds=settings.rate_limit_window_seconds,
        )
        for name, method, path, limit in candidates
        if limit > 0
    ]
