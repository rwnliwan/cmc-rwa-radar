"""RWA Radar — the ONLY module that talks to CoinMarketCap.

Written for the "Build with CMC: API Hackathon, Round 2" (Real World Assets
track). Python 3.10+ standard library only.

Endpoints covered (see CMC-RWA-ENDPOINTS.md for the full research):
  map, info, assets/list, quotes/latest, quotes/historical,
  issuers/list, issuers.
market-pairs/list is deliberately NOT implemented: it is Growth+ only and
is unavailable on the hackathon's free Startup tier.

Key handling (design §3.5):
- The API key is read from `.env.local` (key `CMC_API_KEY`) at runtime.
- It is NEVER printed, logged, or included in any returned data.
- If the file/key is missing, every call raises CmcKeyError with the message
  "set CMC_API_KEY in .env.local" — the key value is never shown.

Fail-closed: an error envelope (error_code != "0") raises CmcApiError;
callers must keep the last good snapshot and mark it stale — never invent
data. HTTP 429 / 5xx is retried once after a 5 s backoff, then raised.
"""

import http.client
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import cmc_config as cfg


class CmcError(Exception):
    """Base error for the CMC adapter."""


class CmcKeyError(CmcError):
    """No usable API key was found in .env.local."""


class CmcApiError(CmcError):
    """The CMC API answered with a non-zero error_code (or a failed HTTP
    status after the one allowed retry)."""

    def __init__(self, message, error_code=None, http_status=None):
        super().__init__(message)
        self.error_code = error_code
        self.http_status = http_status


# ---------------------------------------------------------------------------
# Key loading — read from .env.local next to this module (or the CWD).
# The key value is returned only to the request builder and is never logged.
# ---------------------------------------------------------------------------

def _load_api_key():
    """Return the CMC API key from .env.local, or raise CmcKeyError."""
    candidates = [Path(__file__).resolve().parent / cfg.ENV_FILE,
                  Path.cwd() / cfg.ENV_FILE]
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == cfg.ENV_KEY_NAME:
                value = value.strip().strip('"').strip("'")
                if value:
                    return value
    raise CmcKeyError("set CMC_API_KEY in .env.local")


# ---------------------------------------------------------------------------
# HTTP core
# ---------------------------------------------------------------------------

def _get_json(path, params):
    """GET <BASE_URL><path>?<params> with the API-key header.

    Returns the decoded JSON envelope (dict with "data" + "status").
    Raises CmcApiError on an error envelope or on a failed HTTP status
    (after one retry for 429 / 5xx). Raises CmcKeyError if no key is set.
    """
    api_key = _load_api_key()
    query = urllib.parse.urlencode(
        {k: v for k, v in params.items() if v is not None}, doseq=True)
    url = cfg.BASE_URL + path + ("?" + query if query else "")
    request = urllib.request.Request(url, method="GET", headers={
        "X-CMC_PRO_API_KEY": api_key,
        "Accept": "application/json",
        "User-Agent": cfg.USER_AGENT,
    })
    attempts = 0
    while True:
        attempts += 1
        try:
            with urllib.request.urlopen(
                    request, timeout=cfg.REQUEST_TIMEOUT_SECONDS) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
                status = payload.get("status", {})
                code = status.get("error_code")
                message = status.get("error_message") or body
            except (ValueError, AttributeError):
                code, message = None, body
            if exc.code in (429,) or exc.code >= 500:
                if attempts <= cfg.MAX_RETRIES:
                    time.sleep(cfg.RETRY_BACKOFF_SECONDS)
                    continue
            raise CmcApiError(
                "CMC HTTP %s on %s: %s" % (exc.code, path, message),
                error_code=code, http_status=exc.code) from exc
        except urllib.error.URLError as exc:
            if attempts <= cfg.MAX_RETRIES:
                time.sleep(cfg.RETRY_BACKOFF_SECONDS)
                continue
            raise CmcApiError(
                "CMC request to %s failed: %s" % (path, exc.reason)) from exc
        except (TimeoutError, ConnectionError) as exc:
            # Transport timeout / read failure (23 Nov 2026 re-gate,
            # must-fix #1): a server that answers headers then stalls
            # the body makes urllib raise TimeoutError (socket.timeout)
            # out of resp.read() — NOT a URLError, so the URLError
            # branch above never sees it, and the raw TimeoutError
            # escaped the CmcError path the monitor catches. A reset
            # or dropped connection mid-read surfaces the same way
            # (ConnectionResetError / RemoteDisconnected, both
            # ConnectionError subclasses). Normalise both to
            # CmcApiError, with the same one-retry policy as URLError.
            # Deliberately NOT a bare `except Exception`: a programming
            # bug (TypeError, AttributeError, ...) must still crash
            # loudly instead of being relabelled an API error.
            if attempts <= cfg.MAX_RETRIES:
                time.sleep(cfg.RETRY_BACKOFF_SECONDS)
                continue
            raise CmcApiError(
                "CMC request to %s timed out or dropped: %s"
                % (path, exc)) from exc
        except (http.client.HTTPException, ssl.SSLError) as exc:
            # Truncated body / TLS failure (24 Nov 2026, DeepSeek
            # final review Q1c): http.client.IncompleteRead (a body
            # cut off mid-read) is an HTTPException, NOT an OSError,
            # and ssl.SSLError is an OSError but NOT a ConnectionError
            # — so both escaped the monitor's CmcError path before
            # this branch. Same one-retry policy as the transport
            # branch above; still no bare `except Exception`.
            if attempts <= cfg.MAX_RETRIES:
                time.sleep(cfg.RETRY_BACKOFF_SECONDS)
                continue
            raise CmcApiError(
                "CMC request to %s failed mid-response: %s"
                % (path, exc)) from exc
        except ValueError as exc:
            # A 200 whose body is not valid JSON (or not UTF-8) is a
            # malformed response, not a crash: wrap it in CmcApiError
            # so the monitor's fail-closed path catches it. (Before
            # this, json.JSONDecodeError escaped the CmcError path
            # entirely.) No retry: the server answered, its body is
            # unusable.
            raise CmcApiError(
                "CMC returned invalid JSON on %s: %s" % (path, exc)
                ) from exc
        break

    if not isinstance(payload, dict):
        raise CmcApiError(
            "CMC returned a non-object JSON envelope on %s" % path)
    status = payload.get("status", {})
    if not isinstance(status, dict):
        # 23 Nov 2026 re-gate, must-fix #1: a 200 whose status is
        # null or a list used to reach `status.get(...)` below and
        # raise AttributeError — outside the CmcError path the
        # monitor catches. A wrong-shaped envelope is an API error,
        # not a crash.
        raise CmcApiError(
            "CMC returned a non-object 'status' envelope on %s" % path)
    if str(status.get("error_code", "0")) != "0":
        # 403 code 1014 = historical request out of the plan's window:
        # the caller should lower count/interval, never repeat the call.
        raise CmcApiError(
            "CMC error %s on %s: %s" % (
                status.get("error_code"), path,
                status.get("error_message") or "unknown error"),
            error_code=status.get("error_code"))
    # The pipeline only ever reads data.rwa_assets (see
    # cmc_pipeline.assets_from_envelope): a wrong-typed `data` or
    # `rwa_assets` would raise AttributeError / iterate keys downstream
    # — again outside the monitor's CmcError path. Missing keys stay
    # legal (they read as "no assets"); only wrong TYPES are rejected.
    data = payload.get("data")
    if data is not None and not isinstance(data, dict):
        raise CmcApiError(
            "CMC returned a non-object 'data' envelope on %s" % path)
    rwa_assets = data.get("rwa_assets") if isinstance(data, dict) else None
    if rwa_assets is not None and not isinstance(rwa_assets, list):
        raise CmcApiError(
            "CMC returned a non-list 'data.rwa_assets' envelope on %s"
            % path)
    # 24 Nov 2026, DeepSeek final review Q1b: a list whose ELEMENTS
    # are not objects (e.g. ["a", 1]) passes the list check above,
    # then `asset.get(...)` downstream raises AttributeError — the
    # same class this fix round closes. Every element must be a dict.
    if rwa_assets is not None and not all(
            isinstance(a, dict) for a in rwa_assets):
        raise CmcApiError(
            "CMC returned a non-object element in 'data.rwa_assets' "
            "on %s" % path)
    return payload


def _ids_param(rwa_id=None, rwa_slug=None, symbol=None):
    """One identifier type per request (design §3.5 / research notes)."""
    given = [("rwa_id", rwa_id), ("rwa_slug", rwa_slug), ("symbol", symbol)]
    given = [(k, v) for k, v in given if v is not None]
    if len(given) > 1:
        raise ValueError("pass exactly one of rwa_id, rwa_slug, symbol")
    return dict(given)


# ---------------------------------------------------------------------------
# Endpoints (all return the raw CMC envelope; callers read data + status)
# ---------------------------------------------------------------------------

def fetch_map(symbol=None, rwa_id=None, rwa_slug=None, asset_type=None,
             sort=None, start=None, limit=None):
    """GET /v5/real-world-assets/map — resolve tickers to rwa_id. 0 credits."""
    params = {"asset_type": asset_type, "sort": sort,
              "start": start, "limit": limit}
    params.update(_ids_param(rwa_id=rwa_id, rwa_slug=rwa_slug,
                             symbol=symbol))
    return _get_json(cfg.ENDPOINTS["map"], params)


def fetch_info(rwa_id=None, rwa_slug=None, symbol=None):
    """GET /v5/real-world-assets/info — static metadata + company fields."""
    return _get_json(cfg.ENDPOINTS["info"],
                     _ids_param(rwa_id=rwa_id, rwa_slug=rwa_slug,
                                symbol=symbol))


def fetch_list(asset_type=None, sort=None, start=None, limit=None,
              convert=None):
    """GET /v5/real-world-assets/assets/list — ranked assets with aggregate
    quotes. 1 credit per 250 assets."""
    return _get_json(cfg.ENDPOINTS["assets_list"], {
        "asset_type": asset_type, "sort": sort,
        "start": start, "limit": limit, "convert": convert})


def fetch_quotes_latest(rwa_id=None, rwa_slug=None, symbol=None,
                        convert=None):
    """GET /v5/real-world-assets/quotes/latest — aggregates + tokens[] +
    tradfi_markets[]. 1 credit per 250 assets."""
    params = {"convert": convert}
    params.update(_ids_param(rwa_id=rwa_id, rwa_slug=rwa_slug,
                             symbol=symbol))
    return _get_json(cfg.ENDPOINTS["quotes_latest"], params)


def fetch_historical(rwa_id=None, rwa_slug=None, symbol=None,
                     interval=None, count=None,
                     time_start=None, time_end=None, convert=None):
    """GET /v5/real-world-assets/quotes/historical — time series of tokenised
    aggregates. 1 credit per 100 data points."""
    params = {"interval": interval, "count": count,
              "time_start": time_start, "time_end": time_end,
              "convert": convert}
    params.update(_ids_param(rwa_id=rwa_id, rwa_slug=rwa_slug,
                             symbol=symbol))
    return _get_json(cfg.ENDPOINTS["quotes_historical"], params)


def fetch_issuers_list(start=None, limit=None, active=None):
    """GET /v5/real-world-assets/issuers/list — issuer roster. 1 credit."""
    return _get_json(cfg.ENDPOINTS["issuers_list"], {
        "start": start, "limit": limit, "active": active})


def fetch_issuer(issuer_id):
    """GET /v5/real-world-assets/issuers — one issuer + its tokens. 1 credit."""
    if not issuer_id:
        raise ValueError("issuer_id is required")
    return _get_json(cfg.ENDPOINTS["issuers"], {"issuer_id": issuer_id})
