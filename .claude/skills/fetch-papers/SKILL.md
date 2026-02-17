---
name: fetch-papers
description: Fetch the latest cs.AI papers from arXiv and save to CSV. Use when the user asks to fetch, download, or get new papers from arXiv, or says "論文を取得" or similar.
---

# Fetch Papers

Fetch cs.AI papers from arXiv using `fetch_papers.py` and save them to `data/abstracts.csv`.

## Workflow

1. Calculate the target date as **2 days before today** (arXiv results are available with a ~2 day delay).
2. Run the fetch command:
   ```bash
   uv run python fetch_papers.py --date YYYY-MM-DD
   ```
3. Report how many papers were fetched and saved.
4. If 0 papers are returned (e.g. weekend submissions), try the previous day and explain why.

## Notes

- The script appends to `data/abstracts.csv` and skips duplicates automatically.
- arXiv has no submissions on weekends; if the target date falls on a weekend, step back to the most recent weekday.
- The arXiv API has rate limits; the script handles retries with exponential backoff.
