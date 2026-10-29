# EMG Moraware MCP Server

An [MCP](https://modelcontextprotocol.io) server that gives Claude conversational access to a countertop fabricator's job and scheduling system (Moraware JobTracker). Each tool is a thin HTTP client over **EMGBridge**, a separate ASP.NET service that owns the Moraware session ([moraware-bridge](https://github.com/SanyaBoroda4/moraware-bridge)).

The team asks things like *"what's the square footage on the Carter job?"*, *"find the next open install day"* or *"who is 843-555-1234?"*, and Claude answers from live company data.

> This is a sanitized snapshot of a private repository; the public history is one commit per snapshot, never the private history. The tool code matches the version in production; the snapshot also carries a docstring-only change (11 tools labelled READ-ONLY) that is not deployed yet.
> The production endpoint requires a bearer token; this mirror uses placeholders.

## Numbers

All measured on this snapshot on 2026-10-29.

| What | Value | Command |
|---|---|---|
| MCP tools | **40** | `python -c "import asyncio, emg_mcp; print(len(asyncio.run(emg_mcp.mcp.list_tools())))"` |
| Tools that can write | **1** (`create_activity`, `dry_run=True` by default) | `python -c "import asyncio, emg_mcp; print([t.name for t in asyncio.run(emg_mcp.mcp.list_tools()) if 'dry_run' in t.inputSchema['properties']])"` |
| Tests | **49** (no network; the bridge is an `httpx.MockTransport`) | `pytest -q` |

## Tools

| Area | Tools |
|---|---|
| Jobs | `find_job_by_name`, `find_job_by_address`, `jobs_list`, `job_overview`, `job_details`, `job_timeline`, `job_change_log`, `square_footage` |
| Files, quotes, orders | `job_files`, `job_file_content`, `job_quotes`, `job_orders` |
| Accounts and customers | `account_find`, `account_details`, `account_jobs`, `customer_by_phone` |
| Invoices | `invoice_by_job`, `job_by_invoice` |
| Scheduling | `calendar`, `next_open_day`, `list_scheduled_activities`, `assignees`, `create_activity` |
| Follow-ups | `list_stale_jobs`, `followup_status` |
| Materials | `material_search`, `material_list`, `jobs_by_salesperson` |
| Reports and views | `list_reports`, `run_report`, `saved_views` |
| Reference data | `activity_types`, `activity_statuses`, `job_statuses`, `form_templates`, `appointment_types` |
| Introspection and health | `moraware_capabilities`, `moraware_object`, `cache_status`, `moraware_web_login_status` |

## Design notes

- **Docstrings are the product.** Each docstring is written for the model: when to pick this tool over a similar one, to resolve a name to a job ID before acting, what edge cases mean (cache staleness, ambiguous matches, sentinel dates), and when to stop and ask the person.
- **One write tool, preview first.** `create_activity` returns a preview and writes nothing unless called with `dry_run=False`; its docstring tells the model to show the preview and get an explicit yes first. It takes a job ID, never a name. Every other tool is labelled `READ-ONLY`, and the tests enforce both rules.
- **Errors the model can explain.** When the bridge is unreachable or answers without JSON, tools return an `Error` / `ErrorCode` pair (`BRIDGE_UNAVAILABLE`) instead of raising, matching the bridge's own error codes.
- **Thin client.** The server holds no Moraware credentials and no business logic; the bridge owns the session, the cache and the indexes.
- **DNS-rebinding protection.** Over streamable HTTP, only the configured public host is accepted (`MCP_PUBLIC_HOST`); any other `Host` header gets HTTP 421.

## Run it

```
pip install -r requirements-dev.txt
pytest -q
```

| Setting | Default | Meaning |
|---|---|---|
| `EMG_BRIDGE_URL` | `https://bridge.example.com` | EMGBridge base URL |
| `MCP_PUBLIC_HOST` | `mcp.example.com` | Hostname clients use; the DNS-rebinding allowlist |

- **Streamable HTTP:** `python emg_mcp.py` listens on `0.0.0.0:8000` at `/mcp`. Or with Docker: copy `docker-compose.example.yml` to `docker-compose.yml`, set the values, then `docker compose up --build`. Put a TLS-terminating reverse proxy in front.
- **Clients:** add `https://<your MCP_PUBLIC_HOST>/mcp` as a remote MCP server (for example, a claude.ai custom connector).

CI (`.github/workflows/ci.yml`) runs the tests, prints the tool count and builds the Docker image on every push.

## How it's built

Built with [Claude Code](https://claude.com/claude-code) from my specs and work orders. I own the requirements, the tool design, the deployment and the production debugging. Claude Code wrote most of the code and tests under that direction.
