"""Serving the React operator console at /console (console plan Parts 9 and 14).

The console is a client-routed SPA under one subpath, so the interesting cases
are about ROUTING and CACHING rather than content: does a deep link reach the
shell, does it stop claiming paths that belong to the API, and can a stale copy
survive a deploy.

Part 14 moved it from the interim /console-app to /console and deleted the three
hand-written operator pages, which makes two more things worth pinning: the old
addresses still lead somewhere, and `/console` does not shadow the operator API
— every one of those routes (`/admin/*`, `/temples/*`, `/bookings/*`) lives at
the root, not under the console.
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
    r = await api.get("/console")
    assert r.status_code == 503
    assert "app-console" in r.json()["detail"]


async def test_a_deep_link_reaches_the_shell(api):
    """react-router owns everything under the prefix, so /console/bookings must
    serve the same shell rather than 404 — a bookmarked section is the normal
    way an operator returns to work."""
    if not _console_built():
        pytest.skip("console not built")
    for path in ("/console", "/console/", "/console/people/users"):
        assert (await api.get(path)).status_code == 200, path


async def test_it_does_not_swallow_the_api(api):
    """The mount is scoped to a subpath precisely so a catch-all cannot turn a
    typo'd API call into an HTML 200."""
    r = await api.get("/admin/users")
    assert r.status_code == 401  # the auth wall, not the console shell
    assert "text/html" not in r.headers.get("content-type", "")


async def test_the_retired_pages_lead_somewhere(api):
    """Part 14 deleted admin.html, console.html and whatsapp.html.

    Bookmarks and the banner older `python main.py` runs printed still point at
    those addresses, and an operator who follows one deserves the new tool
    rather than a dead end. 308, so a browser stops asking.
    """
    admin = await api.get("/admin")
    assert admin.status_code == 308
    assert admin.headers["location"] == "/console"

    for path in ("/whatsapp", "/wa"):
        r = await api.get(path)
        assert r.status_code == 308, path
        assert r.headers["location"] == "/console/channels/whatsapp", path


async def test_the_redirect_does_not_eat_the_admin_api(api):
    """`GET /admin` is a page address; `POST /admin/login` is a real route.

    A redirect registered for every method, or on a prefix rather than the exact
    path, would send a login POST to the console and 308 it — which a client
    follows as a GET, losing the body and the credentials with it.
    """
    r = await api.post("/admin/login", json={"username": "x", "password": "y"})
    assert r.status_code != 308
    assert (await api.get("/admin/config")).status_code == 200


async def test_the_interim_address_is_gone(api):
    """/console-app existed for six days between Parts 9 and 14 and is now a
    subpath of nothing. It must 404 like any other typo rather than quietly
    still working — two addresses for one tool is how half the team ends up
    bookmarking the one that will break next."""
    assert (await api.get("/console-app")).status_code == 404


async def test_the_shell_is_never_cached(api):
    """Including deep links. Exact-matching "/console" would leave
    /console/bookings cacheable, which is how an operator ends up looking at
    yesterday's build after a deploy."""
    if not _console_built():
        pytest.skip("console not built")
    for path in ("/console", "/console/bookings/payments"):
        r = await api.get(path)
        assert r.headers["cache-control"] == "no-store", path


async def test_hashed_assets_are_cached_hard(api):
    """Vite content-hashes these, so the filename changes whenever the bytes do.

    They live under /console/assets/, which the consumer app's bare /assets/
    prefix would miss — leaving them with no cache header at all. And the
    no-store rule for "/console" would otherwise catch them, since it is a
    prefix match: the immutable rule is checked first for exactly this reason.
    """
    if not _console_built():
        pytest.skip("console not built")
    from app.main import _CONSOLE_DIR

    asset = next((_CONSOLE_DIR / "assets").glob("*.js"), None)
    assert asset is not None, "a built console always emits a hashed js bundle"
    r = await api.get(f"/console/assets/{asset.name}")
    assert r.status_code == 200
    assert "immutable" in r.headers["cache-control"]
    # The assets mount is registered BEFORE the catch-all. If that order flipped
    # every bundle would be served the HTML shell — with a 200 — and the console
    # would boot to a blank page with no clue why.
    assert "javascript" in r.headers.get("content-type", "")


async def test_the_consumer_app_is_untouched(api):
    """Neither Part 9 nor Part 14 may disturb app-nithara. The SPA root and its
    own routes keep answering exactly as before."""
    for path in ("/", "/poojas", "/astro", "/profile"):
        r = await api.get(path)
        # 200 when built, 503 when not — either way it is the SPA's own answer,
        # not the console's, and not a 404 from a mis-ordered mount.
        assert r.status_code in (200, 503), path
