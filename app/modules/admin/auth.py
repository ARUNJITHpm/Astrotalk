"""Admin access control — moved to app/platform/admin_auth.py.

The guard became cross-cutting once the content module's review endpoints
needed it too, so it lives in platform/ now (modules must not import each
other's internals — AGENTS.md). This shim keeps existing imports working.
"""

from app.platform.admin_auth import AdminGuard, admin_required, require_admin

__all__ = ["AdminGuard", "admin_required", "require_admin"]
