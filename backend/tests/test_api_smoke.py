"""API-level smoke tests.

These assert the app wiring: routers mounted, prefixes correct, auth enforced.
They do not require a live database — the lifespan tolerates a failed migration.
"""


def test_root_reports_service_name(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_openapi_schema_is_served(client):
    assert client.get("/openapi.json").status_code == 200


def test_all_expected_routers_are_mounted(client):
    paths = client.get("/openapi.json").json()["paths"]
    for expected in (
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/me",
        "/api/workspace",
        "/api/workspace/company",
        "/api/workspace/{collection}",
        "/api/workspace/{collection}/{item_id}",
        "/api/workspace/{collection}/bulk",
        "/api/workspace/invoices/with-ledger",
        "/api/workspace/invoices/{item_id}/pay",
        "/api/compute/dashboard",
        "/api/compute/compliance",
        "/api/compute/muhai-score",
        "/api/compute/forecast",
        "/api/compute/tax-summary",
        "/api/compute/payroll",
        "/api/compute/classify",
        "/api/compute/ocr",
        "/api/compute/chat",
        "/api/bank/status",
        "/api/bank/accounts",
        "/api/bank/transactions",
        "/api/bank/import",
        "/api/bank/reconcile",
        "/api/bank/sync",
    ):
        assert expected in paths, f"missing route: {expected}"


def test_the_legacy_user_scoped_routes_are_gone(client):
    """0001-0008 built a per-user API; 0009's workspace replaced all of it.

    Deleted on 2026-09-13. Asserted here so a stray re-import of one of those
    routers cannot quietly put the second, unscoped data surface back.
    """
    paths = client.get("/openapi.json").json()["paths"]
    for gone in (
        "/api/invoices",
        "/api/transactions",
        "/api/employees",
        "/api/products",
        "/api/tax/kdv",
        "/api/muhai-score",
        "/api/dashboard",
        "/api/compliance/alerts",
        "/api/cashflow/forecast",
        "/api/bank-transactions",
        "/api/reminders",
        "/api/predictions/summary",
        "/api/expenses/classify",
        "/api/chat",
    ):
        assert gone not in paths, f"legacy route is back: {gone}"


def test_every_mounted_api_path_belongs_to_a_live_router(client):
    """Four surfaces and nothing else."""
    paths = [p for p in client.get("/openapi.json").json()["paths"] if p.startswith("/api/")]
    assert paths, "no API paths mounted at all"
    for path in paths:
        assert path.startswith(
            ("/api/auth", "/api/workspace", "/api/compute", "/api/bank")
        ), path


def test_protected_endpoint_rejects_anonymous_request(client):
    assert client.post("/api/compute/dashboard", json={}).status_code in (401, 403)


def test_bank_rejects_anonymous_request(client):
    """The bank router holds the deployment's credentials; it is never open."""
    assert client.get("/api/bank/status").status_code in (401, 403)
    assert client.post("/api/bank/sync", json={}).status_code in (401, 403)


def test_workspace_rejects_anonymous_request(client):
    """The workspace is the system of record; it is never open."""
    for path in ("/api/workspace", "/api/workspace/invoices"):
        assert client.get(path).status_code in (401, 403), path


def test_unknown_route_is_404(client):
    assert client.get("/api/does-not-exist").status_code == 404
