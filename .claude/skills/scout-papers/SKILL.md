---
name: scout-papers
description: Review and analyze fetched arXiv cs.AI papers from data/abstracts.csv. Use when the user asks to review, analyze, summarize, or scout papers, or says "論文を確認", "論文をレビュー", "スカウト" or similar. Also use when the user wants to find papers on a specific topic from the fetched data.
---

# Scout Papers

Read and analyze cs.AI papers previously fetched into `data/abstracts.csv`.

## Workflow

1. Read `data/abstracts.csv` to load all fetched papers.
2. Based on user request, perform one of:
   - **Overview**: Summarize all papers grouped by topic/theme, listing count per group.
   - **Topic search**: Filter papers matching the user's interest and present relevant ones.
   - **Detail**: For a specific paper, present title, authors, abstract, and arXiv URL.
3. Present results in a clear table or list format.
   - Always include the arXiv URL for each paper.
   - For summaries, write a 1-line Japanese description of each paper.

## Deep Review Workflow

When asked to do a deep review (detailed summary with commentary):

1. Select papers based on author credibility and abstract quality.
2. Fetch the full paper content. Try sources in order:
   - **HTML**: `https://arxiv.org/html/{arxiv_id}` (via WebFetch)
   - **LaTeX source**: `https://arxiv.org/src/{arxiv_id}` (via WebFetch, if HTML returns 404)
   - **PDF**: `https://arxiv.org/pdf/{arxiv_id}` (via WebFetch, last resort)
3. Write a ~1000 character Japanese summary covering:
   - Problem being addressed
   - Key method/approach with technical details
   - Main results
   - A `## コメント` section with critical commentary and future outlook
4. Save each review to `papers/{yyyy-mm-dd}-{id}.md` where:
   - `yyyy-mm-dd` is the paper's published date
   - `{id}` is the arxiv_id with the dot removed (e.g., `2602.14486` → `260214486`)
   - Include a YAML-style header with title, authors, URL, published date

## CSV Schema

Columns: `arxiv_id`, `published`, `title`, `abstract`, `authors`, `affiliations`, `url`

## Notes

- If `data/abstracts.csv` is empty or missing, suggest running `/fetch-papers` first.
- Papers are in English; summarize in the user's language (default: Japanese).
