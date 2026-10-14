"""Bounded public discovery and asynchronous independent-book reads."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from .config import Config
from .discovery import CLOB, GAMMA
from .panel import queries, select_panel
from .quality import depth_state
from .reconstruction import Engine

Append = Callable[..., dict[str, Any]]


async def discover(
    client: httpx.AsyncClient, config: Config, append: Append, *, update_rates: dict[str, float]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    page_ordinals = []
    now_ns = time.time_ns()
    for stratum, params in queries(
        config.discovery_limit, now_ns, config.selection_seed, config.near_expiry_tag_id
    ):
        response = await client.get(GAMMA + "/markets", params=params)
        received_ns = time.time_ns()
        record = append(
            "discovery_page",
            response.text,
            params=params,
            stratum=stratum,
            endpoint=str(response.url),
            status_code=response.status_code,
            received_ns=received_ns,
        )
        page_ordinals.append(record["ordinal"])
        response.raise_for_status()
        page = response.json()
        if (
            not isinstance(page, list)
            or len(page) > config.discovery_limit
            or any(not isinstance(m, dict) for m in page)
        ):
            raise ValueError("Unbounded or malformed discovery page")
        raw.extend(page)
    selected, audit = select_panel(
        raw, config.markets, now_ns=now_ns, seed=config.selection_seed, update_rates=update_rates
    )
    audit["page_ordinals"] = page_ordinals
    cohort = []
    verification_rejections = []
    for market in selected:
        try:
            response = await client.get(CLOB + "/markets/" + market["condition"])
            record = append(
                "public_market_metadata",
                response.text,
                endpoint=str(response.url),
                status_code=response.status_code,
                market_id=market["id"],
            )
            response.raise_for_status()
            metadata = response.json()
            mapping = {t["token_id"]: t["outcome"].lower() for t in metadata["tokens"]}
            if (
                metadata.get("version") != "v1"
                or metadata.get("condition_id") != market["condition"]
                or mapping != {t: o.lower() for t, o in market["tokens"].items()}
                or metadata.get("closed") is not False
                or metadata.get("accepting_orders") is not True
                or metadata.get("neg_risk") != market["negative_risk"]
            ):
                raise ValueError("Public market mapping/lifecycle/negative-risk disagreement")
            market["metadata_ordinal"] = record["ordinal"]
            market["categories"] = sorted(set(metadata.get("tags") or market["categories"]))
            market["public_market_constraints"] = {
                k: metadata.get(k)
                for k in (
                    "minimum_order_size",
                    "minimum_tick_size",
                    "seconds_delay",
                    "end_date_iso",
                )
            }
            fee_records = {}
            for token in market["tokens"]:
                response = await client.get(CLOB + "/fee-rate", params=dict(token_id=token))
                record = append(
                    "public_fee_metadata",
                    response.text,
                    asset_id=token,
                    endpoint=str(response.url),
                    status_code=response.status_code,
                )
                response.raise_for_status()
                base = response.json()["base_fee"]
                if not isinstance(base, int) or isinstance(base, bool) or base < 0:
                    raise ValueError("Invalid public base_fee")
                fee_records[token] = dict(base_fee=base, raw_ordinal=record["ordinal"])
            market["fee_regime"]["public_base_fee_evidence"] = fee_records
            market["fee_regime"]["status"] = (
                "public_parameters_recorded_formula_requires_declared_version"
            )
            cohort.append(market)
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as error:
            verification_rejections.append(dict(id=market["id"], reason=str(error)))
    audit["verification_rejections"] = verification_rejections
    return cohort, audit


async def independent_book(
    client: httpx.AsyncClient, engine: Engine, asset: str, condition: str, timeout: float
) -> dict[str, Any]:
    before = depth_state(engine.books.get(asset))
    request_ns, request_mono_ns = time.time_ns(), time.monotonic_ns()
    try:
        response = await client.get(CLOB + "/book", params=dict(token_id=asset), timeout=timeout)
        received_ns, received_mono_ns = time.time_ns(), time.monotonic_ns()
        after = depth_state(engine.books.get(asset))
        text = response.text
        if len(text.encode()) > 1024**2:
            raise ValueError("Independent response exceeds one MiB")
        return dict(
            payload=text,
            status_code=response.status_code,
            endpoint=str(response.url),
            asset=asset,
            condition=condition,
            request_ns=request_ns,
            response_ns=received_ns,
            request_monotonic_ns=request_mono_ns,
            response_monotonic_ns=received_mono_ns,
            before=before,
            after=after,
        )
    except (httpx.HTTPError, ValueError) as error:
        return dict(
            payload=None,
            asset=asset,
            condition=condition,
            request_ns=request_ns,
            response_ns=time.time_ns(),
            error=f"{type(error).__name__}: {error}",
        )
