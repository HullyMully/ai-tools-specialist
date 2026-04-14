import json
import os
from pathlib import Path
from typing import Any

import requests


ENV_PATH = Path(".env")
ORDERS_PATH = Path("mock_orders.json")
CREATE_ORDER_PATH = "/api/v5/orders/create"


def load_env(env_path: Path) -> dict[str, str]:
    """Load KEY=VALUE pairs from .env into a dictionary."""
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def build_create_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}{CREATE_ORDER_PATH}"


def load_orders(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Orders file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("mock_orders.json must contain a JSON array of orders")

    return data


def create_order(
    session: requests.Session,
    create_url: str,
    api_key: str,
    order: dict[str, Any],
    site: str | None,
) -> tuple[bool, str]:
    payload: dict[str, str] = {
        "order": json.dumps(order, ensure_ascii=False),
        "site": site or "",
    }

    response = session.post(
        create_url,
        params={"apiKey": api_key},
        data=payload,
        timeout=20,
    )

    response_text = response.text.strip()
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = None

    if response.status_code >= 400:
        if response_text:
            return False, f"HTTP {response.status_code}: {response_text}"
        return False, f"HTTP {response.status_code}: Empty response body"

    if not isinstance(body, dict):
        if response_text:
            return False, f"Invalid JSON response: {response_text}"
        return False, "Invalid JSON response: empty body"

    created = bool(body.get("success"))

    if created:
        order_id = body.get("id") or body.get("order", {}).get("id")
        return True, f"id={order_id}" if order_id else "success=true"

    if response_text:
        return False, f"API returned success=false: {response_text}"
    return False, "API returned success=false with empty body"


def main() -> None:
    env_values = load_env(ENV_PATH)
    os.environ.update(env_values)

    base_url = os.getenv("RETAILCRM_URL")
    api_key = os.getenv("RETAILCRM_API_KEY")
    site = os.getenv("RETAILCRM_SITE")

    if not base_url or not api_key:
        raise RuntimeError(
            "Set RETAILCRM_URL and RETAILCRM_API_KEY in .env before running this script."
        )

    orders = load_orders(ORDERS_PATH)
    create_url = build_create_url(base_url)

    success_count = 0
    fail_count = 0

    with requests.Session() as session:
        for index, order in enumerate(orders, start=1):
            try:
                ok, details = create_order(session, create_url, api_key, order, site)
                if ok:
                    success_count += 1
                    print(f"[{index}] OK -> {details}")
                else:
                    fail_count += 1
                    print(f"[{index}] FAIL -> {details}")
            except requests.RequestException as exc:
                fail_count += 1
                print(f"[{index}] FAIL -> HTTP error: {exc}")
            except (ValueError, json.JSONDecodeError) as exc:
                fail_count += 1
                print(f"[{index}] FAIL -> Invalid response: {exc}")

    print(f"Done. Success: {success_count}, Fail: {fail_count}, Total: {len(orders)}")


if __name__ == "__main__":
    main()
