# emg_mcp.py — EMGBridge MCP server
# 40 tools total (19 original + 21 read-only "full Moraware picture" tools, 2026-10-16).
# All point at endpoints on the same EMGBridge backend. Only create_activity writes.
#
# Install once:  pip install mcp httpx
# Claude Desktop runs this file automatically once connected.

import base64
import os

from mcp.server.fastmcp import FastMCP, Image
import httpx

__version__ = "1.1.0"

# Base URL of the EMGBridge HTTP API. Placeholder by default; set EMG_BRIDGE_URL.
BASE = os.environ.get("EMG_BRIDGE_URL", "https://bridge.example.com").rstrip("/")

mcp = FastMCP("emg-moraware")
http = httpx.Client(timeout=120)


# ─────────────────────────── ORIGINAL READ TOOLS ───────────────────────────

@mcp.tool()
def find_job_by_name(job_name: str, limit: int = 5) -> dict:
    """Find Moraware jobs by full job name (fuzzy, punctuation-tolerant).
    Use this when the user names a customer or job, e.g. "find the John Carter job".
    Returns matches newest-first. In the result: NameMatchStrength "strong" means a
    confident single match; if Ambiguous is true the input was vague, so ask the user
    to confirm before acting. (CreationDate may show 0001-01-01 when answered from the
    cache — don't treat that as a real date.) READ-ONLY."""
    r = http.post(f"{BASE}/api/checkbot/find-job-by-name",
                  json={"job_name": job_name, "limit": limit})
    return r.json()


@mcp.tool()
def list_stale_jobs(limit: int = 0) -> dict:
    """List "stale" jobs that may need a follow-up: a job with a Template/Measure/Quote
    milestone in the past (within the last 6 months), no Install or Removal ever, and no
    future milestone. Results are sorted oldest-first ("most silent first").
    limit > 0 does a quick partial scan; limit = 0 does a full scan (slow — can take a
    few minutes). Use a small limit like 25 for quick questions. READ-ONLY."""
    url = f"{BASE}/api/stalejobs/candidates"
    if limit > 0:
        url += f"?limit={limit}"
    r = http.get(url, timeout=600)
    return r.json()


@mcp.tool()
def followup_status(job_id: int, activity_id: int) -> dict:
    """Read ONE activity's current status and notes, live and uncached (so it reflects
    edits made minutes ago). Use this to check whether a manager acted on a follow-up:
    StatusId 3 ("Complete") means it's done; changed Notes also count as acted-on. READ-ONLY."""
    r = http.get(f"{BASE}/api/stalejobs/followup-status",
                 params={"jobId": job_id, "activityId": activity_id})
    return r.json()


@mcp.tool()
def invoice_by_job(job_id: int) -> dict:
    """Get the QuickBooks invoice number(s) for a given Moraware job id. READ-ONLY."""
    r = http.post(f"{BASE}/api/checkbot/invoice-by-job", json={"jobId": job_id})
    return r.json()


@mcp.tool()
def job_by_invoice(invoice_number: str) -> dict:
    """Find the Moraware job that carries a given QuickBooks invoice number. READ-ONLY."""
    r = http.post(f"{BASE}/api/checkbot/job-by-invoice",
                  json={"invoiceNumber": invoice_number})
    return r.json()


@mcp.tool()
def activity_types() -> dict:
    """List all Moraware activity type IDs and their names (e.g. 17 = Follow Up,
    10 = Quote, 4 = Install). Use this when you need to translate a type id to a name. READ-ONLY."""
    r = http.get(f"{BASE}/api/checkbot/activity-types")
    return r.json()


@mcp.tool()
def cache_status() -> dict:
    """Check EMGBridge cache health: record count, last refresh time, and whether the
    last refresh succeeded. Use this to confirm the backend is up and the data is fresh. READ-ONLY."""
    r = http.get(f"{BASE}/api/cache/status")
    return r.json()


# ─────────────────────────── SCHEDULING / JOBINFO TOOLS ───────────────────────────

@mcp.tool()
def square_footage(job_id: int, include_raw_fields: bool = False) -> dict:
    """Get the per-area square footage for a job. Use when the user asks specifically
    about a job's square footage, e.g. "what's the square footage for [job]". Returns
    each area with its room type and Sq Ft, plus a total. Pass job_id — resolve the job
    name first with find_job_by_name. (For ALL fields on a job's forms, use job_details
    instead.) READ-ONLY."""
    params: dict = {"jobId": job_id}
    if include_raw_fields:
        params["includeRawFields"] = "true"
    r = http.get(f"{BASE}/api/jobinfo/square-footage", params=params)
    return r.json()


@mcp.tool()
def job_details(job_id: int) -> dict:
    """Read ALL fields on ALL of a job's forms — the full Job Summary and Details forms
    (and any others). Use when the user wants the complete picture of a job, e.g. "tell
    me everything about [job]", "what's the edge/backsplash/material on this job?", or
    "is the material ordered / is it paid in full?". Returns every field grouped by form
    (form name + template + name/value pairs), including blank fields and checklist
    checkboxes (Deposit received, Template Ready, Material Ordered, etc.) with their
    state. Pass job_id — resolve the job name first with find_job_by_name. READ-ONLY."""
    r = http.get(f"{BASE}/api/jobinfo/job-details", params={"jobId": job_id})
    return r.json()


@mcp.tool()
def job_quotes(job_id: int, include_totals: bool = True) -> dict:
    """Get all quotes for a job, WITH totals and pricing. Use when the user asks about
    quotes or quote money, e.g. "what did we quote this customer?", "how much is the
    quote on [job]?", "what's the total price?", "when does the quote expire?", or
    "how many revisions?". Returns JobId, QuoteCount, and each quote's name, status,
    price list, salesperson, created date, revision number/date, quote URL, total price,
    square footage, and expiration date. Set include_totals=False for a faster response
    when prices/totals aren't needed (skips per-quote detail fetches). If DetailError is
    set on a quote, the totals could not be read for that quote — report the error rather
    than treating the price as absent. TotalsAvailable says whether every total was read.
    Quotes live in CounterGo and are read from Moraware's web pages with the bridge's own
    web login (it signs in again automatically). If ErrorCode is SESSION_NOT_CONFIGURED,
    SESSION_EXPIRED or LOGIN_FAILED, report that plain Reason rather than reporting no
    quotes. Pass job_id — resolve the job name first with find_job_by_name. READ-ONLY."""
    params: dict = {}
    if not include_totals:
        params["includeTotals"] = "false"
    r = http.get(f"{BASE}/api/job/{job_id}/quotes", params=params)
    return r.json()


@mcp.tool()
def job_timeline(job_id: int, include_history: bool = False) -> dict:
    """Get the full activity timeline/history for ONE job — every activity in order
    (templates, measures, quotes, installs, follow-ups, etc.) with date, time, type,
    status, assignee, and notes. Use when the user wants a job's history or what's
    happened / what's scheduled on a specific job, e.g. "show me the timeline for [job]"
    or "what's the history on this job?". Pass job_id — resolve the job name first with
    find_job_by_name.
    Each activity also has: AssigneeNames/AssigneeIds/AssigneeDisplay (every person
    assigned — the "Assigned To" column; AssigneeId/AssigneeName hold the first one),
    Duration, IsLate + Flags (Moraware's moon icon means "Late": dated before today
    and still open), StatusColor and StatusType. Assignees come from Moraware's job
    page: if AssigneeSource is "unavailable", say so (AssigneeNote explains why)
    instead of claiming nobody is assigned. include_history=True adds CreatedAt/By and
    LastModifiedAt/By per activity from the job's Change Log. READ-ONLY."""
    params: dict = {"jobId": job_id}
    if include_history:
        params["includeHistory"] = "true"
    r = http.get(f"{BASE}/api/scheduler/job-activities", params=params)
    return r.json()


@mcp.tool()
def assignees() -> dict:
    """List all Moraware crew/assignees with their IDs and active status. Use to look up
    who's in the system, or to resolve a person's name to their ID (e.g. "Mark" → 35)
    before scheduling. Returns each person {AssigneeId, AssigneeName, IsInactive}. Some
    names are inactive (IsInactive: true) — don't assign work to those. READ-ONLY."""
    r = http.get(f"{BASE}/api/crew/assignees")
    return r.json()


@mcp.tool()
def next_open_day(activity_type: str, from_date: str | None = None,
                  max_per_day: int = 2, skip_weekends: bool = True,
                  search_limit_days: int = 60) -> dict:
    """Find the next available day to schedule a FIELD activity (Template, Measure,
    Install, or Removal). Use when the user wants the soonest open slot, e.g. "find the
    next open day for a template". A day counts as open if it currently has max_per_day
    (default 2) or fewer of that activity — so up to a 3rd can still be added. Skips
    weekends by default. activity_type is the name, e.g. "Template". from_date
    ("yyyy-MM-dd") defaults to tomorrow. The backend does the counting and returns the
    date plus how many are already booked. READ-ONLY. Note: this reads the cache index
    (refreshed ~every 30 min), so a template booked directly in Moraware in the last few
    minutes may not be counted yet."""
    params: dict = {"typeName": activity_type, "maxPerDay": max_per_day,
                    "skipWeekends": str(skip_weekends).lower(),
                    "searchLimitDays": search_limit_days}
    if from_date:
        params["from"] = from_date
    r = http.get(f"{BASE}/api/scheduler/next-open-day", params=params)
    return r.json()


@mcp.tool()
def list_scheduled_activities(activity_type: str, from_date: str, to_date: str,
                              assignee_id: int | None = None) -> dict:
    """List scheduled activities of a given type across all jobs in a date range
    (reads the cache schedule index). Use to see what's already booked, e.g. "what
    templates are scheduled next week?". activity_type is the name, e.g. "Template",
    "Measure", "Install", "Removal". from_date and to_date are "yyyy-MM-dd". READ-ONLY.
    Reflects the bridge's activity index (rebuilt by the daily cache refresh), so a very
    recent direct Moraware booking may not appear yet — LiveOnlyCount says how many are on
    the live calendar but not in the index (use the calendar tool to see everything).
    Each row also has ActivityId, Time, StatusName/StatusColor, IsLate, Notes, and — joined
    from the live calendar — AssigneeNames/AssigneeIds/AssigneeDisplay and Duration
    (AssigneeSource "unavailable" + AssigneeNote when the bridge's web login is missing).
    (For ONE job's full history, use job_timeline instead.)"""
    params: dict = {"typeName": activity_type, "from": from_date, "to": to_date}
    if assignee_id is not None:
        params["assigneeId"] = assignee_id
    r = http.get(f"{BASE}/api/scheduler/activities", params=params)
    return r.json()


@mcp.tool()
def create_activity(job_id: int, activity_type: str, start_date: str,
                    start_time: str = "09:00", assignee_id: int | None = None,
                    assignee_name: str | None = None,
                    status_id: int = 2, notes: str = "", dry_run: bool = True) -> dict:
    """Create ONE activity (any type) on a job, dated and timed. DEFAULTS TO PREVIEW
    (dry_run=True): it returns exactly what it WOULD create and writes nothing. Only call
    with dry_run=False AFTER the user has seen the preview and explicitly confirms.
    First resolve the job with find_job_by_name and confirm if Ambiguous — this takes a
    concrete job_id, never a name. activity_type is the name, e.g. "Template" or
    "Follow Up". start_date is "yyyy-MM-dd"; start_time is "HH:mm" (default 09:00).
    For the assignee, pass EITHER assignee_id (a number) OR assignee_name (e.g. "Mark") —
    the backend resolves the name to an active assignee (use the assignees tool if
    unsure). Use this to schedule a template, measure, install, follow-up, etc."""
    body: dict = {"jobId": job_id, "activityTypeName": activity_type,
                  "startDate": start_date, "startTime": start_time,
                  "statusId": status_id, "dryRun": dry_run}
    if assignee_id is not None:
        body["assigneeId"] = assignee_id
    if assignee_name:
        body["assigneeName"] = assignee_name
    if notes:
        body["notes"] = notes
    r = http.post(f"{BASE}/api/scheduler/create-activity", json=body)
    return r.json()



@mcp.tool()
def material_search(name: str, from_date: str = "", to_date: str = "", limit: int = 50) -> dict:
    """Search all EMG jobs (full history) by countertop MATERIAL NAME, e.g. "Calacatta
    Premata", "aurora", "taj mahal". Case-insensitive substring match against the
    Material Name field on each job's Details form. Returns matching jobs with job name,
    all material names, total sqft, install dates (latest first), status, and Moraware
    URL. Use from_date/to_date (yyyy-MM-dd) to limit by install date, e.g. this month.
    Check the Coverage block: if InitialBuildComplete is false the index is still
    filling and counts may be partial. Answers questions like "when did we last install
    X?" (first result) and "how many jobs used X this month?" (count with from_date). READ-ONLY."""
    params: dict = {"name": name, "limit": limit}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    r = http.get(f"{BASE}/api/materials/search", params=params)
    return r.json()

@mcp.tool()
def material_list(limit: int = 200) -> dict:
    """List every distinct countertop material name across ALL EMG jobs (full history),
    with job counts and total square footage per material. Use this to discover what
    materials exist / how names are spelled before searching, or for questions like
    "what materials do we use most?". Check Coverage: partial until
    InitialBuildComplete is true. READ-ONLY."""
    r = http.get(f"{BASE}/api/materials/list", params={"limit": limit})
    return r.json()



@mcp.tool()
def jobs_by_salesperson(salesperson: str, natural_stone: bool = False, materials: str = "", installed_before: str = "", installed_after: str = "", limit: int = 200) -> dict:
    """Find jobs by SALESPERSON combined with material and install-date filters — the
    power query for lists like "Alex's natural-stone jobs due for resealing" or
    "Dana's quartzite jobs from the last 6 months". salesperson is a case-insensitive
    name match (e.g. "alex" finds "Alex S."). Set natural_stone=True to match ALL
    natural stone — the category words (granite, marble, quartzite, dolomite, soapstone)
    OR any specific stone name in the shop's natural-stone list (Taj Mahal, Carrara,
    Fantasy Brown, etc.); this catches jobs where the manager typed only the stone name.
    OR pass materials as a comma-separated substring list to match specific materials
    (e.g. "quartzite,dolomite"). installed_before / installed_after (yyyy-MM-dd) filter
    by the job's LATEST install date — installed_before finds jobs last installed on or
    before that date (use for resealing/overdue lists), installed_after for recent work.
    Returns each job with salesperson, matched + all material names, why it matched
    (MatchReasons), total sqft, latest install date, all install dates, status, and
    Moraware URL, sorted latest-install-first. Check Coverage and SalespersonCoverage
    for completeness. READ-ONLY."""
    params: dict = {"salesperson": salesperson, "limit": limit}
    if natural_stone:
        params["naturalStone"] = "true"
    if materials:
        params["materials"] = materials
    if installed_before:
        params["installedBefore"] = installed_before
    if installed_after:
        params["installedAfter"] = installed_after
    r = http.get(f"{BASE}/api/materials/by-salesperson", params=params)
    return r.json()


@mcp.tool()
def customer_by_phone(phone: str) -> dict:
    """Look up EMG customers/jobs by phone number. Use when the user gives a phone
    number and wants to know which customer or job it belongs to, e.g. "who is
    843-555-1234?" or "look up the customer at (843) 555-1234". Accepts the number in
    any format — parentheses, dashes, and spaces are stripped — and matches on the
    LAST 4 DIGITS, so partial numbers ending in the right 4 digits work too. Returns
    the matching customer(s)/job(s) from the bridge; multiple matches are possible
    since only the last 4 digits are compared, so confirm with the user if more than
    one comes back. READ-ONLY."""
    digits = "".join(c for c in phone if c.isdigit())
    r = http.post(f"{BASE}/api/lookup/by-phone",
                  json={"lastFourDigits": digits[-4:]})
    return r.json()


# ─────────────── FULL MORAWARE PICTURE — READ-ONLY TOOLS (2026-10-16) ───────────────
# Every answer carries Source ("live"/"cache") and AsOfUtc. Failures come back as
# {"Error": plain words, "ErrorCode": NOT_FOUND | SESSION_NOT_CONFIGURED |
# SESSION_EXPIRED | LOGIN_FAILED | MORAWARE_UNAVAILABLE | NOT_SUPPORTED | BAD_REQUEST |
# BRIDGE_UNAVAILABLE ...} — explain the ErrorCode to the user instead of guessing.

def _get(path: str, params: dict | None = None, timeout: float = 120) -> dict:
    """GET a bridge endpoint; never raise — a transport/HTTP failure becomes an
    Error/ErrorCode dict like the bridge's own errors."""
    try:
        r = http.get(f"{BASE}{path}", params=params or {}, timeout=timeout)
    except httpx.HTTPError as ex:
        return {"Error": f"The EMG bridge did not answer: {ex}", "ErrorCode": "BRIDGE_UNAVAILABLE"}
    try:
        return r.json()
    except ValueError:
        return {"Error": f"The EMG bridge returned HTTP {r.status_code} without JSON.",
                "ErrorCode": "BRIDGE_UNAVAILABLE"}


@mcp.tool()
def job_overview(job_id: int) -> dict:
    """Everything at the top of a Moraware job page, read live: job name, URL,
    creation date, salesperson, special comment, notes, process + list ("Jobs",
    "Dones", "Jobs on Holds", ...), status (Active/Complete), the ACCOUNT (id, name,
    link), the full JOB ADDRESS block (name line, street, city/state/zip, every phone
    with its label, every email, and free-text lines such as "Sister Ann" in
    OtherLines, plus a Google Maps link), the account address, and every account /
    job contact. Use for "who is this customer / what account / what's their phone,
    email, address, salesperson on job X?". Pass job_id — resolve a name first with
    find_job_by_name. READ-ONLY."""
    return _get(f"/api/job/{job_id}/overview")


@mcp.tool()
def job_files(job_id: int, include_countergo: bool = True) -> dict:
    """List every file attached to a job: the job's Files section (name, type, size,
    upload date, phase, description), files on its Moraware purchase orders, and —
    when include_countergo — files attached to its CounterGo quotes and orders (names
    only). Job/account/purchase-order files have a FileId: pass it to job_file_content
    to actually read a PDF or photo. READ-ONLY."""
    params = {} if include_countergo else {"includeCounterGo": "false"}
    return _get(f"/api/job/{job_id}/files", params)


@mcp.tool()
def job_file_content(file_id: int, kind: str = "job"):
    """Open ONE Moraware file so you can read it: kind is "job" (default), "account"
    or "po" (purchase order) — take file_id from job_files or account_details.
    Images come back as images you can look at; PDFs as text when the server can
    extract it, otherwise as an attached PDF; text files as text. Files over 5 MB
    return just their details and a link. READ-ONLY."""
    info = _get(f"/api/files/{file_id}", {"kind": kind, "info": "true"})
    if info.get("Error"):
        return info
    size = info.get("Size") or 0
    if size > 5 * 1024 * 1024:
        info["Note"] = "Too large to open here (over 5 MB); open it in Moraware."
        return info
    try:
        r = http.get(f"{BASE}/api/files/{file_id}", params={"kind": kind}, timeout=180)
    except httpx.HTTPError as ex:
        return {"Error": f"The EMG bridge did not answer: {ex}", "ErrorCode": "BRIDGE_UNAVAILABLE"}
    ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ctype == "application/json":
        return r.json()
    name = info.get("Name") or f"file-{file_id}"
    data = r.content
    if ctype.startswith("image/"):
        fmt = ctype.split("/", 1)[1]  # FastMCP builds the MIME type as image/{format}
        return [f"{name} ({info.get('SizeDisplay')})", Image(data=data, format=fmt)]
    if ctype.startswith("text/") or name.lower().endswith((".txt", ".csv")):
        return {"FileId": file_id, "Name": name, "ContentType": ctype,
                "Text": data.decode("utf-8", errors="replace")[:60000]}
    if ctype == "application/pdf" or name.lower().endswith(".pdf"):
        try:
            import io
            from pypdf import PdfReader  # optional dependency
            reader = PdfReader(io.BytesIO(data))
            text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
            return {"FileId": file_id, "Name": name, "ContentType": ctype,
                    "Pages": len(reader.pages), "Text": text[:60000]}
        except Exception:
            from mcp.types import BlobResourceContents, EmbeddedResource
            return [f"{name} (PDF, {info.get('SizeDisplay')})",
                    EmbeddedResource(type="resource", resource=BlobResourceContents(
                        uri=f"{BASE}/api/files/{file_id}?kind={kind}", mimeType="application/pdf",
                        blob=base64.b64encode(data).decode("ascii")))]
    return {"FileId": file_id, "Name": name, "ContentType": ctype, "Size": len(data),
            "Note": "Binary file type that can't be shown here; open it in Moraware."}


@mcp.tool()
def job_orders(job_id: int, include_details: bool = True) -> dict:
    """Orders on a job: Moraware purchase orders (number, supplier, status, order and
    expected delivery dates, lines with quantities/costs, files) AND the CounterGo
    orders shown in the job page's Orders section (price, sq ft, sale date, areas with
    phase/material/splash/edge; with include_details also order name, payment status,
    salesperson, QuickBooks export status, payment terms, notes, total). Use for "was
    material ordered / what's on the order / is the order paid?". READ-ONLY."""
    params = {} if include_details else {"includeDetails": "false"}
    return _get(f"/api/job/{job_id}/orders", params)


@mcp.tool()
def job_change_log(job_id: int, limit: int = 50, offset: int = 0) -> dict:
    """The job's Change Log — who changed what and when, newest first: each entry has
    When (Moraware time, US Eastern), By (user), Kind/ObjectName/ObjectId (activity,
    quote, form, address, or the job itself), Action (Created/Updated/Deleted) and
    Changes [{Field, From, To}] — e.g. status, start date, assignee, notes, revision.
    Use for "who moved this install?", "when was this marked complete?", "who changed
    the assignee?". Page with limit/offset (HasMore). READ-ONLY."""
    return _get(f"/api/job/{job_id}/change-log", {"limit": limit, "offset": offset})


@mcp.tool()
def calendar(from_date: str, to_date: str, activity_types: str = "", assignee: str = "",
             live: bool = False, limit: int = 150, offset: int = 0) -> dict:
    """Everything on Moraware's Calendar between from_date and to_date ("yyyy-MM-dd",
    at most 31 days): ALL job activities AND non-job appointments (e.g. "WES OFF",
    "Costco Roadshow"). Each entry: Date, Time (24h) or Unscheduled, Duration,
    ActivityType, StatusName + StatusColor, JobId/JobName (or AppointmentTitle),
    Assignees, Notes. Days gives each date's count and the hours total Moraware prints
    in the day header (e.g. 9.5). Optional filters: activity_types as a comma list of
    names ("Install,Template", "Appointment") and assignee (a name like "Mark" or an
    id). Cached up to 2 minutes; live=True forces a fresh read. If Degraded is true the
    live calendar was unavailable (DegradedReason) and only indexed job activities are
    shown — no appointments, assignees or hours. Page with limit/offset. READ-ONLY."""
    params: dict = {"from": from_date, "to": to_date, "limit": limit, "offset": offset}
    if activity_types:
        params["activityTypes"] = activity_types
    if assignee:
        params["assignee"] = assignee
    if live:
        params["live"] = "true"
    return _get("/api/calendar", params)


@mcp.tool()
def account_find(name: str, limit: int = 25) -> dict:
    """Find Moraware ACCOUNTS (customers/builders/contractors) by name, partial names
    allowed. Returns AccountId, name, link, status, salesperson, how many jobs the
    account has and its newest job. Then use account_details or account_jobs.
    READ-ONLY."""
    return _get("/api/accounts/find", {"name": name, "limit": limit})


@mcp.tool()
def account_details(account_id: int) -> dict:
    """One account in full: name, link, accounting id, status, salesperson, notes, the
    address block (phones, emails, free-text lines), every contact (name, phones,
    emails, notes), account files (FileId for job_file_content with kind="account"),
    custom fields and job count. READ-ONLY."""
    return _get(f"/api/accounts/{account_id}")


@mcp.tool()
def account_jobs(account_id: int = 0, name: str = "", limit: int = 25, offset: int = 0) -> dict:
    """All jobs of ONE account, newest first — critical for builder/contractor payments
    where one account has many jobs. Each job: id, name, link, creation date, list
    (Jobs/Dones/...), status, salesperson, InvoiceNumbers, LatestActivity and
    NextActivity. Pass account_id (from account_find) or the account name; an
    ambiguous name returns Candidates to choose from. READ-ONLY."""
    if account_id:
        return _get(f"/api/accounts/{account_id}/jobs", {"limit": limit, "offset": offset})
    return _get("/api/accounts/jobs", {"name": name, "limit": limit, "offset": offset})


@mcp.tool()
def find_job_by_address(text: str, limit: int = 25) -> dict:
    """Find jobs by ADDRESS: street (with or without number), city or zip, e.g.
    "1418 Harbor", "Harbor Blvd", "29400", "West Ashley". Suffixes and directions are
    normalized (Rd = Road, W = West) and the last word may be partial. Returns best
    matches first, then newest, each with job id, name, account, list, status,
    salesperson, creation date and address. Covers every job in every list. READ-ONLY."""
    return _get("/api/jobs/by-address", {"text": text, "limit": limit})


@mcp.tool()
def jobs_list(list: str, from_date: str = "", to_date: str = "", limit: int = 50,
              offset: int = 0, live: bool = False, status: str = "") -> dict:
    """Moraware's left-menu job lists: "Measurement", "Leads", "Leads with Layouts",
    "Jobs", "Dones", "Jobs on Holds", "Canceled" (each list is a Moraware process; the
    "Jobs" list shows only jobs that are not Complete, like Moraware's Standard View).
    from_date/to_date ("yyyy-MM-dd") filter by creation date. Each row: job id, name,
    account, salesperson, status, creation date, latest activity, next scheduled
    activity, invoice numbers. Served from the daily cache (newest first); live=True
    pages Moraware directly (without dates). status can override: all/active/complete.
    Total + HasMore for paging. READ-ONLY."""
    params: dict = {"list": list, "limit": limit, "offset": offset}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    if live:
        params["live"] = "true"
    if status:
        params["status"] = status
    return _get("/api/jobs/list", params)


@mcp.tool()
def activity_statuses() -> dict:
    """All activity statuses: id, name, abbreviation, display color, type
    (Active/Complete/Canceled/AutoSchedule) and whether valid for appointments. Use to
    translate a StatusId (e.g. 5 = "Paid in Full and Finished", shown red). READ-ONLY."""
    return _get("/api/reference/activity-statuses")


@mcp.tool()
def job_statuses() -> dict:
    """The job lists/processes (Measurement, Leads, Leads with Layouts, Jobs, Dones,
    Jobs on Holds, Canceled) with ids, menu links and how each list is defined, plus
    Moraware's two job statuses (Active, Complete). READ-ONLY."""
    return _get("/api/reference/job-statuses")


@mcp.tool()
def form_templates(include_fields: bool = True) -> dict:
    """Moraware form templates (e.g. "Job Summary", "Details") with every field name
    and type — what job_details can return. READ-ONLY."""
    return _get("/api/reference/form-templates", {"includeFields": str(include_fields).lower()})


@mcp.tool()
def appointment_types() -> dict:
    """Moraware has no appointment types (appointments are titled calendar entries);
    this returns that explanation plus the statuses valid for appointments. Read the
    appointments themselves with the calendar tool. READ-ONLY."""
    return _get("/api/reference/appointment-types")


@mcp.tool()
def saved_views(page: str = "") -> dict:
    """Moraware's saved views (from the Views menus of the Jobs, Calendar, Accounts and
    PurchaseOrder pages): id, name, page and type. page filters, e.g. "Calendar".
    READ-ONLY."""
    return _get("/api/reference/views", {"page": page} if page else None)


@mcp.tool()
def moraware_capabilities() -> dict:
    """What Claude can read from Moraware: every object type moraware_object accepts
    (with the API method behind it, what the id means, and the object's fields), the
    web-only objects, which tool covers what, and what is NOT readable. Start here when
    unsure where a piece of Moraware data lives. READ-ONLY."""
    return _get("/api/explorer/capabilities")


@mcp.tool()
def moraware_object(object_type: str, object_id: int = 0) -> dict:
    """Read ANY single Moraware object by type and id, size-capped (~60 KB) with every
    public property: e.g. "job", "account", "activity", "contact", "job-file",
    "purchase-order", "form", "form-template", "series", "assignee", "salesperson",
    "process", "page-view", "supplier", "serial-number", plus "quote" and "order"
    (CounterGo, by quote/order id). See moraware_capabilities for the full list and what
    each id means. Only read methods are reachable. READ-ONLY."""
    return _get("/api/explorer/object", {"type": object_type, "id": object_id})


@mcp.tool()
def list_reports() -> dict:
    """Moraware's saved reports (left menu "Reports"): id and name. Run one with
    run_report. READ-ONLY."""
    return _get("/api/reports")


@mcp.tool()
def run_report(name: str = "", report_id: int = 0, page: int = 1, page_size: int = 100) -> dict:
    """Run a saved Moraware report by name (partial OK) or report_id, with its saved
    filters and date range (shown in the answer; custom parameters aren't supported).
    Returns Columns, Rows (each row also carries JobId/AccountId when it links to
    one), FirstRow/LastRow/TotalRows and HasMore — page with page/page_size (max 200).
    READ-ONLY."""
    params: dict = {"page": page, "pageSize": page_size}
    if report_id:
        params["reportId"] = report_id
    else:
        params["name"] = name
    return _get("/api/reports/run", params, timeout=180)


@mcp.tool()
def moraware_web_login_status() -> dict:
    """Whether the bridge's own Moraware web login works (mode, user, last sign-in,
    last error). Assignees, calendar appointments/hours, quotes, the Change Log and
    reports need it — check this when those come back SESSION_NOT_CONFIGURED,
    SESSION_EXPIRED or LOGIN_FAILED. READ-ONLY."""
    return _get("/api/diag/web-session")


from mcp.server.transport_security import TransportSecuritySettings

# Public hostname the server is reached at (DNS-rebinding protection). Set MCP_PUBLIC_HOST.
PUBLIC_HOST = os.environ.get("MCP_PUBLIC_HOST", "mcp.example.com")

if __name__ == "__main__":
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = 8000
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[PUBLIC_HOST, f"{PUBLIC_HOST}:*"],
        allowed_origins=[f"https://{PUBLIC_HOST}", f"https://{PUBLIC_HOST}:*"],
    )
    mcp.run(transport="streamable-http")
