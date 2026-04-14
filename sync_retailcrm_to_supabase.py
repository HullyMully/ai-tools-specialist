import json
import os
from pathlib import Path
from typing import Any

import requests
from supabase import Client, create_client


ENV_PATH = Path(".env")
RETAILCRM_ORDERS_PATH = "/api/v5/orders"
PER_PAGE = 100


def load_env(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_orders_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}{RETAILCRM_ORDERS_PATH}"


def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_KEY in .env")
    return create_client(supabase_url, supabase_key)


def fetch_orders_page(
    session: requests.Session,
    orders_url: str,
    api_key: str,
    page: int,
) -> dict[str, Any]:
    response = session.get(
        orders_url,
        params={"apiKey": api_key, "page": page, "limit": PER_PAGE},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_all_orders(base_url: str, api_key: str) -> list[dict[str, Any]]:
    orders_url = build_orders_url(base_url)
    all_orders: list[dict[str, Any]] = []
    page = 1
    total_pages: int | None = None

    with requests.Session() as session:
        while True:
            payload = fetch_orders_page(session, orders_url, api_key, page)
            page_orders = payload.get("orders", [])
            if not isinstance(page_orders, list):
                raise ValueError("RetailCRM response has invalid 'orders' format")

            all_orders.extend(page_orders)
            print(f"RetailCRM: page {page}, fetched {len(page_orders)} orders")

            pagination = payload.get("pagination", {})
            if isinstance(pagination, dict):
                raw_total_pages = pagination.get("totalPageCount")
                if isinstance(raw_total_pages, int):
                    total_pages = raw_total_pages

            if total_pages is not None and page >= total_pages:
                break

            if len(page_orders) < PER_PAGE:
                break

            page += 1

    return all_orders


def map_order_for_upsert(order: dict[str, Any]) -> dict[str, Any]:
    external_id = order.get("externalId")
    if not external_id:
        external_id = str(order.get("id", "")).strip()

    if not external_id:
        raise ValueError("Order does not have 'externalId' or 'id'")

    # Склеиваем имя и фамилию в одно поле customer_name
    first_name = order.get("firstName", "")
    last_name = order.get("lastName", "")
    customer_name = f"{first_name} {last_name}".strip() or "Неизвестный покупатель"

    return {
        "external_id": str(external_id),
        "total_sum": order.get("totalSumm", 0), # Обрати внимание: в CRM это totalSumm, а в базе total_sum
        "status": order.get("status", "new"),
        "customer_name": customer_name
        # id и created_at мы не передаем — база данных заполнит их сама
    }


def upsert_orders(supabase: Client, orders: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    skipped = 0

    for order in orders:
        try:
            rows.append(map_order_for_upsert(order))
        except ValueError as exc:
            skipped += 1
            print(f"Skip order: {exc}")

    if not rows:
        print("No valid orders for upsert.")
        return

    for start in range(0, len(rows), 500):
        chunk = rows[start : start + 500]
        supabase.table("orders").upsert(chunk, on_conflict="external_id").execute()
        print(f"Supabase: upserted {len(chunk)} rows")

    if skipped:
        print(f"Skipped orders without external id: {skipped}")


def main() -> None:
    os.environ.update(load_env(ENV_PATH))

    retailcrm_url = os.getenv("RETAILCRM_URL")
    retailcrm_api_key = os.getenv("RETAILCRM_API_KEY")

    if not retailcrm_url or not retailcrm_api_key:
        raise RuntimeError("Set RETAILCRM_URL and RETAILCRM_API_KEY in .env")

    supabase = get_supabase_client()
    orders = fetch_all_orders(retailcrm_url, retailcrm_api_key)
    print(f"RetailCRM: total fetched orders = {len(orders)}")
    upsert_orders(supabase, orders)
    print("Sync completed.")


if __name__ == "__main__":
    main()
