"""Conservative public-username existence checks.

Design constraints (non-negotiable):
- One username per interactive invocation by default; no bulk mode.
- Only a small curated set of providers with documented, stable URL
  patterns and per-site verification beyond a bare HTTP 200.
- Never treats HTTP 200 alone as a match (soft-404s are routine).
- Backs off on 429/403/5xx/CAPTCHA — never circumvents.
- Existence of a public handle is NOT identity attribution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from tracefield.core.domain import UsernameResultState

REQUEST_TIMEOUT_S = 10.0
MIN_INTERVAL_S = 1.0  # polite rate limit between requests
USER_AGENT = "tracefield/0.1 (public-profile existence check; contact: local)"


@dataclass(frozen=True)
class ProviderRule:
    """A single provider's verification rule. Inert metadata + a pure
    function; never executable catalogue content."""

    name: str
    url_template: str  # {username} placeholder
    # Patterns that indicate the profile is absent even on HTTP 200 (soft-404).
    not_found_markers: tuple[str, ...] = ()
    # Patterns that indicate a real profile page on HTTP 200.
    found_markers: tuple[str, ...] = ()
    # When true, HTTP 200 with no markers => LIKELY_MATCH (not confirmed).
    presence_on_200: bool = True
    notes: str = ""


# Curated, deliberately tiny. Each rule is documented; expansion requires
# per-site verification testing. These patterns are hypotheses to re-check
# as platforms change — see `checked_at` in the result.
CURATED_PROVIDERS: tuple[ProviderRule, ...] = (
    ProviderRule(
        name="github",
        url_template="https://github.com/{username}",
        not_found_markers=("Not Found", "This is not the web page you are looking for"),
        found_markers=('"profile"', 'itemprop="additionalName"'),
        notes="GitHub returns 404 for missing users; 200+markers => confirmed.",
    ),
    ProviderRule(
        name="gitlab",
        url_template="https://gitlab.com/{username}",
        not_found_markers=("Page Not Found", "Whoops, not found"),
        found_markers=("gitlab-activity", "js-user-profile"),
        notes="GitLab 404s missing users; verify body markers on 200.",
    ),
    ProviderRule(
        name="reddit",
        url_template="https://www.reddit.com/user/{username}/about.json",
        not_found_markers=(
            '"message": "Sorry, nobody on Reddit goes by that name"',
            "page not found",
        ),
        found_markers=('"kind": "t2"',),
        presence_on_200=False,  # 200 alone is unreliable; require marker
        notes="Reddit JSON: require kind=t2 marker; 200 alone is unreliable.",
    ),
    ProviderRule(
        name="hackernews",
        url_template="https://news.ycombinator.com/user?id={username}",
        not_found_markers=("No such user.",),
        found_markers=("user:", "created:"),
        notes="HN returns 200 with 'No such user.' for missing accounts (soft-404).",
    ),
    ProviderRule(
        name="keybase",
        url_template="https://keybase.io/{username}",
        not_found_markers=("404", "Sorry, we can't find"),
        found_markers=('"basics"', "keybase.io/"),
        notes="Keybase profile pages; verify markers carefully.",
    ),
)

_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,38}$")


@dataclass
class ProviderResult:
    provider: str
    state: UsernameResultState
    url: str
    http_status: int | None = None
    final_url: str = ""
    evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def validate_username(username: str) -> str:
    if not _USERNAME_RE.match(username):
        raise ValueError(
            "invalid username: must be 1-39 chars of letters, digits, "
            "underscore, dot, or hyphen, starting alphanumeric"
        )
    return username


def _classify(rule: ProviderRule, status: int, body: str) -> ProviderResult:
    url = rule.url_template.format(username="")
    if status == 429:
        return ProviderResult(
            provider=rule.name,
            state=UsernameResultState.RATE_LIMITED,
            url=url,
            http_status=status,
            limitations=["provider rate-limited the request; not retried"],
        )
    if status in (401, 403):
        return ProviderResult(
            provider=rule.name,
            state=UsernameResultState.BLOCKED,
            url=url,
            http_status=status,
            limitations=["access blocked by provider; not circumvented"],
        )
    if status >= 500:
        return ProviderResult(
            provider=rule.name,
            state=UsernameResultState.PROVIDER_ERROR,
            url=url,
            http_status=status,
            limitations=[f"provider server error HTTP {status}"],
        )
    if status == 404:
        return ProviderResult(
            provider=rule.name,
            state=UsernameResultState.NOT_FOUND_VERIFIED,
            url=url,
            http_status=status,
            evidence=[f"HTTP {status}"],
        )
    if status == 200:
        for marker in rule.not_found_markers:
            if marker.lower() in body.lower():
                return ProviderResult(
                    provider=rule.name,
                    state=UsernameResultState.NOT_FOUND_VERIFIED,
                    url=url,
                    http_status=status,
                    evidence=[f"soft-404 marker present: {marker!r}"],
                )
        found = [m for m in rule.found_markers if m.lower() in body.lower()]
        if found:
            return ProviderResult(
                provider=rule.name,
                state=UsernameResultState.CONFIRMED_PUBLIC_PROFILE,
                url=url,
                http_status=status,
                evidence=[f"HTTP 200 + profile markers: {found}"],
            )
        if rule.presence_on_200:
            return ProviderResult(
                provider=rule.name,
                state=UsernameResultState.LIKELY_MATCH,
                url=url,
                http_status=status,
                evidence=["HTTP 200, no explicit profile markers matched"],
                limitations=["HTTP 200 alone is NOT proof of a profile (soft-404 risk)"],
            )
        return ProviderResult(
            provider=rule.name,
            state=UsernameResultState.INCONCLUSIVE,
            url=url,
            http_status=status,
            evidence=["HTTP 200 but rule requires markers and none matched"],
        )
    return ProviderResult(
        provider=rule.name,
        state=UsernameResultState.INCONCLUSIVE,
        url=url,
        http_status=status,
        limitations=[f"unexpected HTTP {status}"],
    )


def check_username(
    username: str,
    providers: list[ProviderRule] | None = None,
    *,
    max_body: int = 500_000,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Check one username against curated public-profile providers.

    Never claims two accounts belong to the same person. Never performs
    logins, credential checks, or safeguard bypasses.
    """
    username = validate_username(username)
    rules = providers if providers is not None else list(CURATED_PROVIDERS)
    results: list[ProviderResult] = []

    owns_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=REQUEST_TIMEOUT_S,
            follow_redirects=True,
            max_redirects=3,
            headers={"User-Agent": USER_AGENT},
            trust_env=False,
        )
    try:
        import time

        from tracefield.security import UrlPolicyError, validate_fetch_url

        for rule in rules:
            url = rule.url_template.format(username=username)
            # Defense in depth: even curated URLs must pass the policy.
            try:
                validate_fetch_url(url)
            except UrlPolicyError as exc:
                results.append(
                    ProviderResult(
                        provider=rule.name,
                        state=UsernameResultState.NOT_CHECKED,
                        url=url,
                        limitations=[f"URL rejected by safety policy: {exc}"],
                    )
                )
                continue
            try:
                resp = client.get(url)
            except httpx.TimeoutException:
                results.append(
                    ProviderResult(
                        provider=rule.name,
                        state=UsernameResultState.PROVIDER_ERROR,
                        url=url,
                        limitations=["request timed out"],
                    )
                )
                time.sleep(MIN_INTERVAL_S)
                continue
            except httpx.HTTPError as exc:
                results.append(
                    ProviderResult(
                        provider=rule.name,
                        state=UsernameResultState.PROVIDER_ERROR,
                        url=url,
                        limitations=[f"network error: {type(exc).__name__}"],
                    )
                )
                time.sleep(MIN_INTERVAL_S)
                continue
            body = resp.text[:max_body]
            r = _classify(rule, resp.status_code, body)
            r.url = url
            r.final_url = str(resp.url)
            results.append(r)
            time.sleep(MIN_INTERVAL_S)
    finally:
        if owns_client:
            client.close()

    return {
        "username": username,
        "results": [
            {
                "provider": r.provider,
                "state": r.state.value,
                "url": r.url,
                "http_status": r.http_status,
                "final_url": r.final_url,
                "evidence": r.evidence,
                "limitations": r.limitations,
            }
            for r in results
        ],
        "caveats": [
            "Existence of a public handle is NOT identity attribution. Reused "
            "usernames, common names, and parody/impersonation accounts are "
            "routine sources of false positives.",
            "These checks only cover the curated provider list; absence from "
            "the list is NOT evidence of absence on the wider internet.",
            "Provider page structures change; states reflect rules recorded "
            "at check time and can go stale.",
        ],
        "checked_rule_count": len(rules),
    }
