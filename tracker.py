#!/usr/bin/env python3
"""Check the Barcelona half-marathon bib marketplace and notify via Telegram."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


MARKETPLACE_URL = (
    "https://inscripciones.rpmsports.es/en/event/"
    "hyundai-mitja-marato-barcelona-by-brooks-2027/transfer-registration"
)
DEFAULT_STATE_PATH = Path("state.json")


@dataclass(frozen=True)
class Listing:
    reference: str
    fee: str
    amount: str
    requires_validation: str
    url: str


class MarketplaceParser(HTMLParser):
    """Extract rows from the marketplace table without third-party packages."""

    def __init__(self) -> None:
        super().__init__()
        self.in_marketplace = False
        self.table_depth = 0
        self.current_row: Optional[list[str]] = None
        self.current_link: Optional[str] = None
        self.current_cell: list[str] = []
        self.rows: list[tuple[list[str], str]] = []
        self._row_link = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()

        if tag == "table" and "table-listados" in classes:
            self.in_marketplace = True
            self.table_depth = 1
            return
        if not self.in_marketplace:
            return
        if tag == "table":
            self.table_depth += 1
        elif tag == "tr" and self.table_depth == 1:
            self.current_row = []
            self._row_link = ""
        elif tag in {"td", "th"} and self.current_row is not None:
            self.current_cell = []
        elif tag == "a" and self.current_row is not None:
            self.current_link = attributes.get("href") or ""

    def handle_endtag(self, tag: str) -> None:
        if not self.in_marketplace:
            return
        if tag in {"td", "th"} and self.current_row is not None:
            self.current_row.append(" ".join("".join(self.current_cell).split()))
            self.current_cell = []
        elif tag == "a":
            self.current_link = None
        elif tag == "tr" and self.current_row is not None:
            if self.current_row and any(self.current_row):
                self.rows.append((self.current_row, self._row_link))
            self.current_row = None
        elif tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_marketplace = False

    def handle_data(self, data: str) -> None:
        if self.current_row is None:
            return
        self.current_cell.append(data)
        link = self.current_link
        if link:
            self._row_link = link


def fetch_marketplace(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "BCN-Half-Marathon-BIB-Tracker/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_listings(html: str, page_url: str = MARKETPLACE_URL) -> list[Listing]:
    parser = MarketplaceParser()
    parser.feed(html)
    listings: list[Listing] = []
    for cells, row_url in parser.rows:
        # Header rows are excluded by requiring the three identifying columns.
        if len(cells) < 3 or cells[0].lower() in {"ref.", "ref"}:
            continue
        values = (cells + [""] * 4)[:4]
        resolved_url = urljoin(page_url, row_url) if row_url else page_url
        listings.append(
            Listing(
                reference=values[0],
                fee=values[1],
                amount=values[2],
                requires_validation=values[3],
                url=resolved_url,
            )
        )
    return listings


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("listing_ids", []))
    except (OSError, json.JSONDecodeError, AttributeError):
        return set()


def listing_id(listing: Listing) -> str:
    return hashlib.sha256(json.dumps(asdict(listing), sort_keys=True).encode()).hexdigest()


def save_state(path: Path, listings: list[Listing]) -> None:
    data = {"listing_ids": sorted(listing_id(listing) for listing in listings)}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def send_telegram(listings: list[Listing], token: str, chat_id: str) -> None:
    lines = ["🏃 Barcelona half-marathon bib available!", ""]
    for listing in listings:
        lines.extend(
            [
                f"Ref: {listing.reference}",
                f"Fee: {listing.fee} | Amount: {listing.amount}",
                listing.url,
                "",
            ]
        )
    payload = urlencode({"chat_id": chat_id, "text": "\n".join(lines)}).encode()
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok"):
            raise RuntimeError("Telegram rejected the notification")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Telegram notification failed: {type(error).__name__}") from error


def main() -> int:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--url", default=MARKETPLACE_URL)
    argument_parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    argument_parser.add_argument("--dry-run", action="store_true")
    args = argument_parser.parse_args()

    try:
        listings = parse_listings(fetch_marketplace(args.url), args.url)
        previous_ids = load_state(args.state)
        new_listings = [item for item in listings if listing_id(item) not in previous_ids]
        print(f"Found {len(listings)} listing(s); {len(new_listings)} new.")

        if not new_listings:
            save_state(args.state, listings)
            return 0
        if args.dry_run:
            print("Dry run: notification and state update skipped.")
            return 0

        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError("New listings found, but Telegram secrets are not configured")
        send_telegram(new_listings, token, chat_id)
        save_state(args.state, listings)
        print("Telegram notification sent.")
        return 0
    except (HTTPError, URLError, TimeoutError) as error:
        print(f"Marketplace check failed: {type(error).__name__}", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
