from __future__ import annotations

from scripts.compare_api_contracts import compare, route_methods


def test_route_method_diff_identifies_added_removed_and_unchanged() -> None:
    existing = {
        "paths": {
            "/api/health": {"get": {}, "parameters": []},
            "/api/paper": {"get": {}, "patch": {}},
        }
    }
    candidate = {
        "paths": {
            "/api/health": {"get": {}, "parameters": []},
            "/api/paper": {"get": {}},
            "/api/observatory": {"get": {}},
        }
    }
    assert route_methods(existing) == {
        ("/api/health", "GET"),
        ("/api/paper", "GET"),
        ("/api/paper", "PATCH"),
    }
    result = compare(existing, candidate)
    assert result["result"] == "COORDINATED_CUTOVER_REQUIRED"
    assert result["added_to_candidate"] == [{"path": "/api/observatory", "method": "GET"}]
    assert result["removed_from_candidate"] == [{"path": "/api/paper", "method": "PATCH"}]


def test_contract_diff_includes_existing_response_and_schema_changes() -> None:
    existing = {
        "paths": {"/api/health": {"get": {"responses": {"200": {"description": "old"}}}}},
        "components": {"schemas": {"Health": {"type": "object"}}},
    }
    candidate = {
        "paths": {"/api/health": {"get": {"responses": {"200": {"description": "new"}}}}},
        "components": {
            "schemas": {
                "Health": {"type": "object", "required": ["status"]},
                "Status": {"type": "string"},
            }
        },
    }

    result = compare(existing, candidate)
    assert result["result"] == "COORDINATED_CUTOVER_REQUIRED"
    assert result["changed_existing_operations"] == [
        {"path": "/api/health", "method": "GET", "fields": ["responses"]}
    ]
    assert result["changed_schemas"] == ["Health"]
    assert result["added_schemas"] == ["Status"]


def test_contract_diff_includes_global_security_and_shared_component_changes() -> None:
    existing = {
        "openapi": "3.1.0",
        "security": [{"oldAuth": []}],
        "servers": [{"url": "/v1"}],
        "paths": {"/api/health": {"get": {"responses": {"200": {"description": "ok"}}}}},
        "components": {"securitySchemes": {"oldAuth": {"type": "http", "scheme": "bearer"}}},
    }
    candidate = {
        "openapi": "3.1.0",
        "security": [{"newAuth": []}],
        "servers": [{"url": "/v2"}],
        "paths": {"/api/health": {"get": {"responses": {"200": {"description": "ok"}}}}},
        "components": {
            "securitySchemes": {"newAuth": {"type": "http", "scheme": "bearer"}},
            "responses": {"Accepted": {"description": "accepted"}},
        },
    }

    result = compare(existing, candidate)
    assert result["result"] == "COORDINATED_CUTOVER_REQUIRED"
    assert result["global_security_changed"] is True
    assert result["servers_changed"] is True
    assert result["changed_security_schemes"] == ["newAuth", "oldAuth"]
    assert result["other_component_changes"]["responses"]["added"] == ["Accepted"]


def test_contract_diff_includes_inherited_path_parameters_and_operation_ids() -> None:
    operation = {"responses": {"200": {"description": "ok"}}, "operationId": "readHealth"}
    existing = {
        "paths": {
            "/api/health": {
                "parameters": [{"name": "tenant", "in": "query", "required": False}],
                "get": operation,
            }
        }
    }
    candidate = {
        "paths": {
            "/api/health": {
                "parameters": [{"name": "tenant", "in": "query", "required": True}],
                "get": {**operation, "operationId": "getHealth"},
            }
        }
    }

    result = compare(existing, candidate)
    assert result["changed_existing_operations"] == [
        {
            "path": "/api/health",
            "method": "GET",
            "fields": ["operationId", "pathParameters"],
        }
    ]
