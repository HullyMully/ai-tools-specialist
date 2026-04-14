import json
import os
from pathlib import Path
from typing import Any

import requests
from supabase import Client, create_client


ENV_PATH = Path(".env")
RETAILCRM_ORDERS_PATH = "/api/v5/orders"
PER_PAGE = 100

# Уведомления о крупных заказах (сумма из CRM — totalSumm)
LARGE_ORDER_THRESHOLD = 50_000
TELEGRAM_NOTIFIED_IDS_PATH = Path("telegram_notified_order_ids.json")


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


def order_customer_name(order: dict[str, Any]) -> str:
    first = str(order.get("firstName", "")).strip()
    last = str(order.get("lastName", "")).strip()
    name = f"{first} {last}".strip()
    return name or "Неизвестный покупатель"


def load_notified_order_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(raw, list):
        return {str(x) for x in raw}
    if isinstance(raw, dict) and "ids" in raw and isinstance(raw["ids"], list):
        return {str(x) for x in raw["ids"]}
    return set()


def save_notified_order_ids(path: Path, ids: set[str]) -> None:
    sorted_ids = sorted(ids, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x))
    path.write_text(
        json.dumps({"ids": sorted_ids}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def send_telegram_message(
    session: requests.Session,
    bot_token: str,
    chat_id: str,
    text: str,
) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = session.post(
        url,
        json={"chat_id": chat_id, "text": text},
        timeout=20,
    )
    response.raise_for_status()


def notify_large_orders_telegram(
    session: requests.Session,
    orders: list[dict[str, Any]],
    state_path: Path,
) -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        print(
            "Telegram: пропуск уведомлений (не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID).",
        )
        return

    notified = load_notified_order_ids(state_path)
    sent = 0

    for order in orders:
        total_raw = order.get("totalSumm")
        try:
            total = float(total_raw) if total_raw is not None else 0.0
        except (TypeError, ValueError):
            total = 0.0

        if total <= LARGE_ORDER_THRESHOLD:
            continue

        crm_id = order.get("id")
        if crm_id is None:
            continue
        order_key = str(crm_id)
        if order_key in notified:
            continue

        name = order_customer_name(order)
        amount_display = int(round(total))
        text = (
            f"Новый крупный заказ! Сумма: {amount_display} ₸, Клиент: {name}"
        )

        try:
            send_telegram_message(session, bot_token, chat_id, text)
            notified.add(order_key)
            save_notified_order_ids(state_path, notified)
            sent += 1
            print(f"Telegram: уведомление отправлено по заказу id={order_key}")
        except requests.RequestException as exc:
            print(f"Telegram: ошибка отправки для заказа id={order_key}: {exc}")

    if sent:
        print(f"Telegram: отправлено уведомлений: {sent}")


def map_order_for_upsert(order: dict[str, Any]) -> dict[str, Any]:
    external_id = order.get("externalId")
    if not external_id:
        external_id = str(order.get("id", "")).strip()

    if not external_id:
        raise ValueError("Order does not have 'externalId' or 'id'")

    customer_name = order_customer_name(order)

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

    state_file = Path(os.getenv("TELEGRAM_STATE_PATH", "").strip() or TELEGRAM_NOTIFIED_IDS_PATH)

    with requests.Session() as tg_session:
        notify_large_orders_telegram(tg_session, orders, state_file)

    print("Sync completed.")


if __name__ == "__main__":
    main()
