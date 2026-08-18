#!/usr/bin/env python3
"""Post-deploy sanity check against a *real* running backend (and
optionally frontend) - not a substitute for backend/tests/ (which is
fast, isolated, and runs on every push in CI against a fake DB/mocked
LLMs), but a check that the actual deployed thing is actually up:
real DNS, real TLS, real Supabase connection, real CORS headers, a real
route round-trip.

Usage:
    python backend/scripts/smoke_test.py
    python backend/scripts/smoke_test.py --base-url http://127.0.0.1:8123 --frontend-url ""

Defaults to the real production URLs. Exits non-zero if any check fails,
so it can gate a deploy script or just be run by hand right after
`render deploys create` / `vercel --prod`.

Deliberately cheap: the one LLM-touching check uses a short, comma-free,
"and"-free description, so it always takes the Groq path (see
_needs_grounding() in app/api/v1/foods.py) - and repeat runs hit the
estimate_cache table anyway. Never touches Gemini's scarce 20/day quota.
"""

import argparse
import sys

import httpx

DEFAULT_BACKEND = "https://calorieparser-backend.onrender.com"
DEFAULT_FRONTEND = "https://frontend-six-khaki-k808d8a0hz.vercel.app"


class Check:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.detail = ""


def run(name, fn) -> Check:
    check = Check(name)
    try:
        detail = fn()
        check.passed = True
        check.detail = detail or "ok"
    except AssertionError as e:
        check.detail = str(e)
    except Exception as e:
        check.detail = f"{type(e).__name__}: {e}"
    return check


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BACKEND, help="Backend base URL")
    parser.add_argument(
        "--frontend-url",
        default=DEFAULT_FRONTEND,
        help="Frontend base URL (pass an empty string to skip frontend checks, e.g. for local-only runs)",
    )
    parser.add_argument("--timeout", type=float, default=45.0, help="Per-request timeout (Render cold starts can take 30-50s)")
    args = parser.parse_args()

    backend = args.base_url.rstrip("/")
    frontend = args.frontend_url.rstrip("/") if args.frontend_url else None
    client = httpx.Client(timeout=args.timeout)

    checks = []

    def check_health():
        r = client.get(f"{backend}/health")
        assert r.status_code == 200, f"expected 200, got {r.status_code}"
        assert r.json().get("status") == "ok", f"unexpected body: {r.text}"
        return f"{r.elapsed.total_seconds():.1f}s"

    checks.append(run("Backend health check", check_health))

    def check_auth_gate():
        r = client.get(f"{backend}/v1/logs")
        assert r.status_code == 401, f"expected 401 for an unauthenticated protected route, got {r.status_code}"
        return "unauthenticated request correctly rejected"

    checks.append(run("Auth gate rejects requests with no token", check_auth_gate))

    def check_estimate_validation():
        r = client.post(f"{backend}/v1/foods/estimate", json={"description": "  "})
        assert r.status_code == 422, f"expected 422 for an empty description, got {r.status_code}"
        return "input validation still enforced"

    checks.append(run("Estimate endpoint rejects an empty description", check_estimate_validation))

    def check_estimate_real_call():
        # Comma-free, "and"-free, <=8 words - _needs_grounding() keeps this
        # on the cheap Groq path (or an instant cache hit on repeat runs),
        # regardless of Gemini's daily quota state.
        r = client.post(f"{backend}/v1/foods/estimate", json={"description": "a medium banana"})
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
        body = r.json()
        assert body.get("items"), f"missing/empty items in response: {body}"
        total = body.get("total", {})
        assert total.get("calories"), f"missing/zero total calories in response: {body}"
        return f"{r.elapsed.total_seconds():.1f}s, {len(body['items'])} item(s), {total.get('calories')} kcal"

    checks.append(run("Estimate endpoint returns a real result (Groq/cache path)", check_estimate_real_call))

    def check_cors_header():
        r = client.options(
            f"{backend}/health",
            headers={
                "Origin": frontend or "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = r.headers.get("access-control-allow-origin")
        assert allow_origin, "no Access-Control-Allow-Origin header on a CORS preflight"
        return f"Access-Control-Allow-Origin: {allow_origin}"

    checks.append(run("CORS preflight returns an Allow-Origin header", check_cors_header))

    if frontend:

        def check_frontend():
            r = client.get(frontend, follow_redirects=True)
            assert r.status_code == 200, f"expected 200, got {r.status_code}"
            assert "CalorieParser" in r.text, "page loaded but doesn't mention CalorieParser - wrong build?"
            return f"{r.elapsed.total_seconds():.1f}s"

        checks.append(run("Frontend is reachable and serves the app", check_frontend))

    width = max(len(c.name) for c in checks)
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        all_passed = all_passed and c.passed
        print(f"[{status}] {c.name.ljust(width)}  {c.detail}")

    print()
    if all_passed:
        print(f"All {len(checks)} checks passed.")
        return 0
    else:
        failed = sum(1 for c in checks if not c.passed)
        print(f"{failed}/{len(checks)} check(s) FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
