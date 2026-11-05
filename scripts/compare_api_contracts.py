#!/usr/bin/env python3
"""Compare the running local API contract with an isolated unified release import."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
CONTRACT_FIELDS = (
    "parameters",
    "requestBody",
    "responses",
    "security",
    "servers",
    "operationId",
    "deprecated",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def route_methods(openapi: dict[str, Any]) -> set[tuple[str, str]]:
    paths = openapi.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI document has no paths object")
    routes: set[tuple[str, str]] = set()
    for path, operations in paths.items():
        if not isinstance(path, str) or not isinstance(operations, dict):
            raise ValueError("OpenAPI paths contain an invalid entry")
        for method in operations:
            if method in HTTP_METHODS:
                routes.add((path, method.upper()))
    return routes


def load_running_openapi(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("existing API URL must use local loopback HTTP")
    try:
        with urlopen(url, timeout=5) as response:
            document = json.load(response)
    except (OSError, URLError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read local API OpenAPI document: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("local API OpenAPI response is not an object")
    return document


def load_candidate_openapi(candidate_root: Path, isolated_root: Path) -> dict[str, Any]:
    candidate_root = candidate_root.expanduser().resolve(strict=True)
    isolated_root = isolated_root.expanduser().absolute()
    if (
        not (candidate_root / "apps/api/main.py").is_file()
        or not (candidate_root / "packages/midas").is_dir()
    ):
        raise ValueError("candidate root must contain the API application and MIDAS packages")
    if isolated_root.exists() and (isolated_root.is_symlink() or not isolated_root.is_dir()):
        raise ValueError("isolated root must be a real directory")
    isolated_root.mkdir(parents=True, exist_ok=True)

    os.environ.update(
        {
            "MIDAS_MODE": "demo",
            "MIDAS_RUNTIME_ROOT": str(isolated_root / "runtime"),
            "MIDAS_DATABASE_URL": f"sqlite+aiosqlite:///{isolated_root / 'midas.db'}",
            "MIDAS_ARENA_ROOT": str(isolated_root / "arena"),
            "MIDAS_LABORATORY_ROOT": str(isolated_root / "laboratory"),
            "MIDAS_RECORDING_ROOT": str(isolated_root / "recordings"),
            "MIDAS_REALITY_WORKSPACE": str(isolated_root / "reality"),
            "MIDAS_VERITAS_WORKSPACE": str(isolated_root / "veritas"),
            "MIDAS_FRONTIER_ROOT": str(isolated_root / "frontier"),
            "MIDAS_FRONTIER_POLYMARKET_PUBLIC_PROBE_ENABLED": "false",
            "MIDAS_FRONTIER_KALSHI_PUBLIC_PROBE_ENABLED": "false",
            "MIDAS_FRONTIER_KRAKEN_PUBLIC_PROBE_ENABLED": "false",
            "MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED": "false",
        }
    )
    sys.path.insert(0, str(candidate_root / "packages"))
    sys.path.insert(0, str(candidate_root))
    from apps.api.main import app

    document = app.openapi()
    if not isinstance(document, dict):
        raise ValueError("candidate API generated an invalid OpenAPI document")
    return document


def compare(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    existing_routes = route_methods(existing)
    candidate_routes = route_methods(candidate)
    added = candidate_routes - existing_routes
    removed = existing_routes - candidate_routes
    changed_operations: list[dict[str, Any]] = []
    for path, method in sorted(existing_routes & candidate_routes):
        old_path = existing["paths"][path]
        new_path = candidate["paths"][path]
        old = old_path[method.lower()]
        new = new_path[method.lower()]
        changed = [
            field
            for field in CONTRACT_FIELDS
            if _canonical(old.get(field)) != _canonical(new.get(field))
        ]
        if _canonical(old_path.get("parameters")) != _canonical(new_path.get("parameters")):
            changed.append("pathParameters")
        if changed:
            changed_operations.append({"path": path, "method": method, "fields": changed})

    old_components = existing.get("components", {})
    new_components = candidate.get("components", {})
    schema_names = {
        name
        for name in set(old_components.get("schemas", {})) | set(new_components.get("schemas", {}))
        if _canonical(old_components.get("schemas", {}).get(name))
        != _canonical(new_components.get("schemas", {}).get(name))
    }
    old_schemes = old_components.get("securitySchemes", {})
    new_schemes = new_components.get("securitySchemes", {})
    changed_security_schemes = sorted(
        name
        for name in set(old_schemes) | set(new_schemes)
        if _canonical(old_schemes.get(name)) != _canonical(new_schemes.get(name))
    )
    added_schemas = sorted(
        set(new_components.get("schemas", {})) - set(old_components.get("schemas", {}))
    )
    removed_schemas = sorted(
        set(old_components.get("schemas", {})) - set(new_components.get("schemas", {}))
    )
    changed_schemas = sorted(schema_names - set(added_schemas) - set(removed_schemas))
    other_component_changes: dict[str, dict[str, list[str]]] = {}
    for section in ("parameters", "responses", "requestBodies", "headers"):
        old_map = old_components.get(section, {})
        new_map = new_components.get(section, {})
        added_items = sorted(set(new_map) - set(old_map))
        removed_items = sorted(set(old_map) - set(new_map))
        changed_items = sorted(
            name
            for name in set(old_map) & set(new_map)
            if _canonical(old_map[name]) != _canonical(new_map[name])
        )
        other_component_changes[section] = {
            "added": added_items,
            "removed": removed_items,
            "changed": changed_items,
        }
    global_security_changed = _canonical(existing.get("security")) != _canonical(
        candidate.get("security")
    )
    servers_changed = _canonical(existing.get("servers")) != _canonical(candidate.get("servers"))
    old_info = existing.get("info", {})
    new_info = candidate.get("info", {})
    changed_info_fields = sorted(
        field for field in ("title", "version") if old_info.get(field) != new_info.get(field)
    )
    openapi_version_changed = existing.get("openapi") != candidate.get("openapi")
    contract_changed = bool(
        added
        or removed
        or changed_operations
        or added_schemas
        or removed_schemas
        or changed_schemas
        or changed_security_schemes
        or any(any(items.values()) for items in other_component_changes.values())
        or global_security_changed
        or servers_changed
        or changed_info_fields
        or openapi_version_changed
    )
    return {
        "existing_openapi_path_count": len(existing.get("paths", {})),
        "candidate_openapi_path_count": len(candidate.get("paths", {})),
        "existing_path_method_count": len(existing_routes),
        "candidate_path_method_count": len(candidate_routes),
        "added_to_candidate": [{"path": path, "method": method} for path, method in sorted(added)],
        "removed_from_candidate": [
            {"path": path, "method": method} for path, method in sorted(removed)
        ],
        "changed_existing_operations": changed_operations,
        "added_schemas": added_schemas,
        "removed_schemas": removed_schemas,
        "changed_schemas": changed_schemas,
        "changed_security_schemes": changed_security_schemes,
        "other_component_changes": other_component_changes,
        "global_security_changed": global_security_changed,
        "servers_changed": servers_changed,
        "changed_info_fields": changed_info_fields,
        "openapi_version_changed": openapi_version_changed,
        "result": "MATCH" if not contract_changed else "COORDINATED_CUTOVER_REQUIRED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--isolated-root", type=Path, required=True)
    parser.add_argument("--existing-url", default="http://127.0.0.1:8000/openapi.json")
    args = parser.parse_args(argv)
    try:
        existing = load_running_openapi(args.existing_url)
        candidate = load_candidate_openapi(args.candidate_root, args.isolated_root)
        result = compare(existing, candidate)
        result["existing_application_version"] = existing.get("info", {}).get("version")
        result["candidate_application_version"] = candidate.get("info", {}).get("version")
        manifest_path = args.candidate_root / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        result["candidate_source_commit"] = manifest.get(
            "source_commit", os.environ.get("MIDAS_SOURCE_REVISION", "unknown")
        )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, KeyError, ImportError) as error:
        print(json.dumps({"result": "FAILED", "error": str(error)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
