"""Print a minimal ONPE network diagnostic for the current runtime."""

from __future__ import annotations

import asyncio
import hashlib
import os
import socket
from contextlib import contextmanager

import httpx


HOST = "resultadoelectoral.onpe.gob.pe"
BASE_API = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-419,es;q=0.9",
    "Content-Type": "application/json",
    "Referer": "https://resultadoelectoral.onpe.gob.pe/main/presidenciales",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


@contextmanager
def _force_host_ip(ip: str | None):
    if not ip:
        yield
        return

    original = socket.getaddrinfo

    def patched(host, port, family=0, type=0, proto=0, flags=0):
        if host == HOST:
            return original(ip, port, family, type, proto, flags)
        return original(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched
    try:
        yield
    finally:
        socket.getaddrinfo = original


def _data_shape(data: object) -> str:
    if isinstance(data, list):
        return f"list:{len(data)}"
    if isinstance(data, dict):
        return "dict:" + ",".join(list(data.keys())[:8])
    return type(data).__name__


async def main() -> None:
    forced_ip = os.getenv("ONPE_FORCE_IP", "").strip()
    if forced_ip:
        print(f"DIAG forced_ip={forced_ip}")
    with _force_host_ip(forced_ip):
        await _run()


async def _run() -> None:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, http2=True, timeout=20) as client:
        try:
            ip = (await client.get("https://api.ipify.org?format=json")).json().get("ip")
        except Exception as exc:
            ip = f"ip_error:{type(exc).__name__}"
        print(f"DIAG source_ip={ip}")

        main_page = await client.get("https://resultadoelectoral.onpe.gob.pe/main/presidenciales")
        print(
            "DIAG main "
            f"status={main_page.status_code} "
            f"http={main_page.http_version} "
            f"len={len(main_page.content)} "
            f"url={main_page.url}"
        )

        process_path = "/proceso/proceso-electoral-activo"
        process_resp = await client.get(f"{BASE_API}{process_path}")
        process_hash = hashlib.sha256(process_resp.content).hexdigest()[:16]
        try:
            process_json = process_resp.json()
            process_json_error = ""
        except Exception as exc:
            process_json = {}
            process_json_error = f" json_error={type(exc).__name__}"
        process_data = process_json.get("data") if isinstance(process_json, dict) else None
        id_eleccion = process_data.get("idEleccionPrincipal", 10) if isinstance(process_data, dict) else 10
        print(
            "DIAG process_probe "
            f"status={process_resp.status_code} http={process_resp.http_version} "
            f"len={len(process_resp.content)} sha={process_hash}{process_json_error}"
        )
        print(f"DIAG id_eleccion={id_eleccion}")

        endpoints = {
            "process": "/proceso/proceso-electoral-activo",
            "totals": f"/resumen-general/totales?idEleccion={id_eleccion}&tipoFiltro=eleccion",
            "mesas": "/mesa/totales?tipoFiltro=eleccion",
            "candidates": (
                "/eleccion-presidencial/participantes-ubicacion-geografica-nombre"
                f"?idEleccion={id_eleccion}&tipoFiltro=eleccion"
            ),
            "heatmap": f"/resumen-general/mapa-calor?idEleccion={id_eleccion}&tipoFiltro=total",
        }

        for name, path in endpoints.items():
            response = await client.get(f"{BASE_API}{path}")
            body_hash = hashlib.sha256(response.content).hexdigest()[:16]
            try:
                payload = response.json()
            except Exception as exc:
                print(
                    f"DIAG {name} status={response.status_code} http={response.http_version} "
                    f"len={len(response.content)} sha={body_hash} json_error={type(exc).__name__}"
                )
                continue

            success = payload.get("success") if isinstance(payload, dict) else None
            data = payload.get("data") if isinstance(payload, dict) else None
            print(
                f"DIAG {name} status={response.status_code} http={response.http_version} "
                f"len={len(response.content)} sha={body_hash} success={success} data={_data_shape(data)}"
            )


if __name__ == "__main__":
    asyncio.run(main())
