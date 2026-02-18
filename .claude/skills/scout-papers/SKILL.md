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
2. Download LaTeX source and extract figures by running:
   ```
   uv run python extract_source.py {arxiv_id} {published_date}
   ```
   This creates `papers/{yyyy-mm-dd}/{id}/` with figure PNG files.
   If extract_source.py fails, fall back to WebFetch:
   - **HTML**: `https://arxiv.org/html/{arxiv_id}`
   - **PDF**: `https://arxiv.org/pdf/{arxiv_id}` (last resort)
3. Read the LaTeX source output (tex_content) to understand the paper's full content.
4. Write a ~1000 character Japanese summary covering:
   - Problem being addressed
   - Key method/approach with technical details
   - Main results
   - A `## コメント` section with critical commentary and future outlook
5. Save each review to `papers/{yyyy-mm-dd}/{id}/{id}.md` where:
   - `yyyy-mm-dd` is the paper's published date
   - `{id}` is the arxiv_id with the dot removed (e.g., `2602.14486` → `260214486`)
   - Include a YAML-style header with title, authors, URL, published date
   - Embed extracted figures in the markdown using relative paths:
     ```
     ![Figure 1: caption](figure1.png)
     ```
   - Include only the most relevant figures (typically Figure 1 and key result figures)

## CSV Schema

Columns: `arxiv_id`, `published`, `title`, `abstract`, `authors`, `affiliations`, `url`

## Notes

- If `data/abstracts.csv` is empty or missing, suggest running `/fetch-papers` first.
- Papers are in English; summarize in the user's language (default: Japanese).
