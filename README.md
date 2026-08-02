# EMG Moraware MCP Server

> ### ⚠️ Reading the commit history? Start here.
> This is the **public mirror of a private production repo** (in daily use at
> the company since June 2026). The private history can't be published as-is —
> it references live internal infrastructure — so the public history begins
> with this scrubbed snapshot. **From here on, every commit to the private
> repo is mirrored here 1:1** (same message, same day). This server is one
> piece of a larger platform — see
> [emg-console-portfolio](https://github.com/SanyaBoroda4/emg-console-portfolio)
> for the main application.

`emg_mcp.py` is an [MCP](https://modelcontextprotocol.io) (Model Context
Protocol) server that gives Claude direct, conversational access to a stone
fabrication company's job/scheduling system (Moraware). It exposes ~16 tools;
each is a thin HTTP client over the **EMGBridge** backend (a separate private
ASP.NET service that owns the Moraware SDK session).

In practice this means the team can ask Claude things like *"what's the square
footage on the Carter job?"*, *"find the next open install day"*, or *"who is
843-555-1234?"* — and Claude answers from live company data.

## Tools

- **Job lookup & info** — `find_job_by_name` (fuzzy, ambiguity-aware),
  `job_details` (every field on every form), `job_timeline`, `square_footage`
- **Materials analytics** — `material_search`, `material_list`,
  `jobs_by_salesperson` (combined salesperson × material × install-date
  queries, e.g. "natural-stone jobs due for resealing")
- **Customers & invoices** — `customer_by_phone` (last-4-digit matching),
  `invoice_by_job`, `job_by_invoice`
- **Scheduling** — `next_open_day`, `list_scheduled_activities`, and
  `create_activity` — the one write tool, which **defaults to a dry-run
  preview** and only writes after explicit human confirmation
- **Ops** — `list_stale_jobs` (follow-up radar), `followup_status`,
  `assignees`, `activity_types`, `cache_status`

## Design notes

- **Docstrings are the product.** Each tool's docstring is written for the
  LLM: when to pick this tool over a similar one, how to resolve names to IDs
  first, what edge cases mean (cache staleness, ambiguous matches, sentinel
  dates), and when to stop and ask the human.
- **Human-in-the-loop writes.** The single mutating tool previews by default
  (`dry_run=True`); the model is instructed to show the preview and get an
  explicit yes before committing.
- **Thin client, smart backend.** The server holds no credentials and no
  business logic — the bridge owns the Moraware session, caching, and
  indexing. (`BASE` here points at a placeholder; the real endpoint is
  internal.)

## Run

```
pip install mcp httpx
```

Point `BASE` at your bridge, then either let Claude Desktop launch it over
stdio, or run it directly as a streamable-HTTP server (see `__main__`, which
also configures DNS-rebinding protection and allowed origins).
