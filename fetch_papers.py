#!/usr/bin/env python3
"""Fetch today's cs.AI papers from arXiv API and save to data/abstracts.csv."""

import argparse
import csv
import os
import sys
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

ARXIV_API_URL = "https://export.arxiv.org/api/query"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "data", "abstracts.csv")
FIELDNAMES = ["arxiv_id", "published", "title", "abstract", "authors", "affiliations", "url"]

CATEGORY = "cs.AI"
MAX_RESULTS_PER_REQUEST = 200
REQUEST_INTERVAL = 3  # seconds between API calls

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
}


MAX_RETRIES = 5
RETRY_BASE_WAIT = 10  # seconds, doubles each retry


def fetch_page(query: str, start: int, max_results: int) -> bytes:
    """Single paginated request to arXiv API with exponential backoff."""
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    url = f"{ARXIV_API_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "arxiv-scout/1.0"})
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == MAX_RETRIES:
                raise
            wait = RETRY_BASE_WAIT * (2 ** (attempt - 1))
            print(f"  Attempt {attempt} failed ({e}), retrying in {wait}s ...")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def parse_entries(xml_data: bytes) -> tuple[list[dict], int]:
    """Parse Atom XML. Returns (entries, totalResults)."""
    root = ET.fromstring(xml_data)
    total = int(root.findtext("opensearch:totalResults", "0", NS))

    entries = []
    for entry in root.findall("atom:entry", NS):
        raw_id = entry.findtext("atom:id", "", NS)
        if "/abs/" not in raw_id:
            continue  # skip feed-level metadata entries

        arxiv_id = raw_id.split("/abs/")[-1]
        published = entry.findtext("atom:published", "", NS)
        title = " ".join(entry.findtext("atom:title", "", NS).split())
        abstract = " ".join(entry.findtext("atom:summary", "", NS).split())

        authors = []
        affiliations = []
        for author in entry.findall("atom:author", NS):
            name = author.findtext("atom:name", "", NS).strip()
            if name:
                authors.append(name)
            affs = [a.text.strip() for a in author.findall("arxiv:affiliation", NS) if a.text]
            affiliations.append("; ".join(affs) if affs else "")

        entries.append({
            "arxiv_id": arxiv_id,
            "published": published,
            "title": title,
            "abstract": abstract,
            "authors": " | ".join(authors),
            "affiliations": " | ".join(affiliations),
            "url": raw_id,
        })
    return entries, total


def fetch_all(target_date: date) -> list[dict]:
    """Fetch all cs.AI papers submitted on target_date."""
    # submittedDate range: full day in GMT
    d_from = target_date.strftime("%Y%m%d") + "0000"
    d_to = (target_date + timedelta(days=1)).strftime("%Y%m%d") + "0000"
    query = f"cat:{CATEGORY} AND submittedDate:[{d_from} TO {d_to}]"

    all_entries: list[dict] = []
    start = 0

    while True:
        print(f"  Querying arXiv API (start={start}) ...")
        xml_data = fetch_page(query, start, MAX_RESULTS_PER_REQUEST)
        entries, total = parse_entries(xml_data)

        all_entries.extend(entries)
        print(f"  Got {len(entries)} entries (total available: {total})")

        if start + MAX_RESULTS_PER_REQUEST >= total or not entries:
            break
        start += MAX_RESULTS_PER_REQUEST
        time.sleep(REQUEST_INTERVAL)

    return all_entries


def load_existing_ids(path: str) -> set[str]:
    """Load arXiv IDs already present in the CSV."""
    ids: set[str] = set()
    if not os.path.exists(path):
        return ids
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.add(row["arxiv_id"])
    return ids


def save_papers(path: str, papers: list[dict], existing_ids: set[str]) -> int:
    """Append new (non-duplicate) papers to CSV. Returns count added."""
    new = [p for p in papers if p["arxiv_id"] not in existing_ids]
    if not new:
        return 0

    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new)
    return len(new)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch today's cs.AI papers from arXiv.")
    parser.add_argument(
        "--date",
        type=lambda s: date.fromisoformat(s),
        default=date.today(),
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    target: date = args.date
    print(f"Target date: {target}")
    print(f"CSV path:    {CSV_PATH}")

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    existing_ids = load_existing_ids(CSV_PATH)
    print(f"Existing entries in CSV: {len(existing_ids)}")

    papers = fetch_all(target)
    print(f"Found {len(papers)} cs.AI papers for {target}.")

    if not papers:
        print("No papers found. Try a different --date (arXiv has no submissions on weekends).")
        sys.exit(0)

    added = save_papers(CSV_PATH, papers, existing_ids)
    print(f"Added {added} new papers to CSV.")
    if len(papers) - added > 0:
        print(f"Skipped {len(papers) - added} duplicates.")


if __name__ == "__main__":
    main()
