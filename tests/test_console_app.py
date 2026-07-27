"""Serving the React operator console at /console-app (console plan Part 9).

The console is a client-routed SPA under one subpath, so the interesting cases
are about ROUTING and CACHING rather than content: does a deep link reach the
shell, does it stop claiming paths that belong to the API, and can a stale copy
survive a deploy.
"""

import httpx
import pytest
from httpx import ASGITransport

from app.main import app as main_app


@pytest.fixture
async def api():
    transport = ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _console_built() -> bool:
    from app.main import _CONSOLE_INDEX

    return _CONSOLE_INDEX.is_file()


async def test_unbuilt_says_so_instead_of_404(api):
    """A 404 sends whoever hits it hunting for a missing route when the real
    answer is that nobody ran the build."""
    if _console_built():
        pytest.skip("console is built in this checkout")
    r = await api.get("/console-app")
    assert r.status_code == 503
    assert "app-console" in r.json()["detail"]


async def test_a_deep_link_reaches_the_shell(api):
    """react-router owns everything under the prefix, so /console-app/bookings
    must serve the same shell rather than 404 — a bookmarked section is the
    normal way an operator returns to work."""
    if not _console_built():
        pytest.skip("console not built")
    for path in ("/console-app", "/console-app/", "/console-app/people/users"):
        assert (await api.get(path)).status_code == 200, path


async def test_it_does_not_swallow_the_api(api):
    """The mount is scoped to a subpath precisely so a catch-all cannot turn a
    typo'd API call into an HTML 200."""
    r = await api.get("/admin/users")
    assert r.status_code == 401  # the auth wall, not the console shell
    assert "text/html" not in r.headers.get("content-type", "")


async def test_the_old_console_still_works(api):
    """/console-app is additive: the hand-written page keeps serving until the
    sections finish migrating (retired in Part 14)."""
    assert (await api.get("/console")).status_code == 200


async def test_the_shell_is_never_cached(api):
    """Including deep links. Exact-matching "/console-app" would leave
    /console-app/bookings cacheable, which is how an operator ends up looking
    at yesterday's build after a deploy."""
    if not _console_built():
        pytest.skip("console not built")
    for path in ("/console-app", "/console-app/bookings/payments"):
        r = await api.get(path)
        assert r.headers["cache-control"] == "no-store", path


async def test_hashed_assets_are_cached_hard(api):
    """Vite content-hashes these, so the filename changes whenever the bytes do.

    They live under /console-app/assets/, which the consumer app's bare
    /assets/ prefix would miss — leaving them with no cache header at all.
    """
    if not _console_built():
        pytest.skip("console not built")
    from app.main import _CONSOLE_DIR

    asset = next((_CONSOLE_DIR / "assets").glob("*.js"), None)
    assert asset is not None, "a built console always emits a hashed js bundle"
    r = await api.get(f"/console-app/assets/{asset.name}")
    assert r.status_code == 200
    assert "immutable" in r.headers["cache-control"]


async def test_the_consumer_app_is_untouched(api):
    """Part 9 must not disturb app-nithara. The SPA root and its own routes
    keep answering exactly as before."""
    for path in ("/", "/poojas", "/astro", "/profile"):
        r = await api.get(path)
        # 200 when built, 503 when not — either way it is the SPA's own answer,
        # not the console's, and not a 404 from a mis-ordered mount.
        assert r.status_code in (200, 503), path
