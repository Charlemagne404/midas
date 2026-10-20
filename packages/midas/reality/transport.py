"""Bound public HTTP bodies before buffering/JSON decoding; no venue semantics."""

import asyncio
from collections.abc import Callable
from typing import Any

import httpx

MAX_HTTP_RESPONSE_BYTES = 2 * 1024**2


async def _bounded_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    append: Callable[..., Any] | None = None,
    limit: int = MAX_HTTP_RESPONSE_BYTES,
    **kwargs: Any,
) -> httpx.Response:
    # Raw streaming plus identity encoding avoids an unbounded decompression
    # allocation before a decoded-body limit can be enforced.
    body = bytearray()
    async with client.stream(
        "GET", url, headers={"Accept-Encoding": "identity"}, **kwargs
    ) as response:
        encoding = response.headers.get("content-encoding", "identity").lower()
        unsupported_encoding = encoding not in {"identity", ""}
        chunks = (
            response.aiter_bytes(chunk_size=64 * 1024)
            if response.is_stream_consumed
            else response.aiter_raw(chunk_size=64 * 1024)
        )
        async for chunk in chunks:
            body.extend(chunk)
            if unsupported_encoding or len(body) > limit:
                if append is not None:
                    import base64

                    append(
                        "http_response_limit",
                        dict(
                            reason="http_response_limit",
                            endpoint=str(response.url),
                            status_code=response.status_code,
                            observed_wire_prefix_base64=base64.b64encode(body).decode(),
                            observed_wire_bytes=len(body),
                            limit_bytes=limit,
                            content_encoding=encoding,
                            limitation="response aborted; remainder not observed",
                        ),
                    )
                raise httpx.HTTPError(
                    "Public response exceeds body budget or uses unsupported encoding"
                )
        # A fresh buffered Response preserves the existing caller API. The raw
        # response remains scoped to the context and always closes on failure.
        return httpx.Response(
            response.status_code,
            headers={
                k: v
                for k, v in response.headers.items()
                if k.lower() not in {"content-encoding", "content-length"}
            },
            content=bytes(body),
            request=response.request,
        )


async def bounded_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    append: Callable[..., Any] | None = None,
    limit: int = MAX_HTTP_RESPONSE_BYTES,
    **kwargs: Any,
) -> httpx.Response:
    # HTTP read timeouts apply per chunk. Also bound a trickling response's total
    # lifetime so discovery cannot hold a source lifecycle open indefinitely.
    deadline = min(30.0, float(kwargs.get("timeout", 20)))
    try:
        async with asyncio.timeout(deadline):
            return await _bounded_get(client, url, append=append, limit=limit, **kwargs)
    except TimeoutError as error:
        raise httpx.ReadTimeout("Public response exceeded total request deadline") from error
