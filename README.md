# arxiv-scout

arXiv の cs.AI カテゴリから最新の論文を自動取得し、Claude AI と連携して論文の分析・レビューを行うツールです。

## 機能

- **論文の自動取得** — arXiv API から cs.AI カテゴリの論文メタデータ（タイトル・著者・アブストラクト等）を取得し CSV に保存
- **論文スカウト** — 取得した論文をトピック別に概観、特定テーマでの絞り込み、詳細レビューの生成
- **ディープレビュー** — 論文の全文を取得し、日本語で約1000文字の要約とコメントを生成して Markdown に保存

## セットアップ

**前提条件**: Python 3.13 以上、[uv](https://docs.astral.sh/uv/)

```bash
git clone <repository-url>
cd arxiv-scout
uv sync
```

## 使い方

### CLI から直接実行

```bash
# 特定の日付の論文を取得（arXiv は公開まで約2日のラグあり）
uv run python fetch_papers.py --date 2026-02-16

# 日付を省略するとデフォルトで今日の日付を使用
uv run python fetch_papers.py
```

取得した論文は `data/abstracts.csv` に追記されます（重複は自動スキップ）。

### Claude Code のスキルとして使用

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) から 2 つのスキルを利用できます。

| スキル | 説明 |
|--------|------|
| `/fetch-papers` | arXiv から最新の cs.AI 論文を取得（2日前の日付を自動計算） |
| `/scout-papers` | 取得済みの論文を分析・レビュー |

```
# 論文を取得
> /fetch-papers

# 論文の概要を確認
> /scout-papers

# 特定トピックで絞り込み
> LLM の最適化に関する論文を探して

# ディープレビューを生成
> 面白そうな論文を5本選んで詳細レビューして
```

## プロジェクト構成

```
arxiv-scout/
├── fetch_papers.py          # arXiv API から論文を取得するスクリプト
├── main.py                  # エントリポイント
├── data/
│   └── abstracts.csv        # 取得した論文メタデータ (CSV)
├── papers/
│   └── *.md                 # ディープレビュー (Markdown)
├── .claude/
│   └── skills/              # Claude Code スキル定義
│       ├── fetch-papers/
│       └── scout-papers/
└── pyproject.toml
```

## データフロー

```
arXiv API (cs.AI)
    ↓  fetch_papers.py
data/abstracts.csv
    ↓  /scout-papers
papers/*.md (日本語レビュー)
```

## 技術的な補足

- 外部ライブラリ不要（Python 標準ライブラリのみ使用）
- arXiv API のレート制限に対応（指数バックオフによるリトライ）
- CSV への追記時に arxiv_id で重複チェック
- arXiv は週末に投稿がないため、土日は前の平日の論文を取得

## ライセンス

Private
