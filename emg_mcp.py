# emg_mcp.py — EMGBridge MCP server
# 12 existing tools + 2 new quick-win reads (assignees, job_timeline) = 14 total.
# All point at endpoints on the same EMGBridge backend.
#
# Install once:  pip install mcp httpx
# Claude Desktop runs this file automatically once connected.

from mcp.server.fastmcp import FastMCP
import httpx

BASE = "https://bridge.example.com"

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
    cache — don't treat that as a real date.)"""
    r = http.post(f"{BASE}/api/checkbot/find-job-by-name",
                  json={"job_name": job_name, "limit": limit})
    return r.json()


@mcp.tool()
def list_stale_jobs(limit: int = 0) -> dict:
    """List "stale" jobs that may need a follow-up: a job with a Template/Measure/Quote
    milestone in the past (within the last 6 months), no Install or Removal ever, and no
    future milestone. Results are sorted oldest-first ("most silent first").
    limit > 0 does a quick partial scan; limit = 0 does a full scan (slow — can take a
    few minutes). Use a small limit like 25 for quick questions."""
    url = f"{BASE}/api/stalejobs/candidates"
    if limit > 0:
        url += f"?limit={limit}"
    r = http.get(url, timeout=600)
    return r.json()


@mcp.tool()
def followup_status(job_id: int, activity_id: int) -> dict:
    """Read ONE activity's current status and notes, live and uncached (so it reflects
    edits made minutes ago). Use this to check whether a manager acted on a follow-up:
    StatusId 3 ("Complete") means it's done; changed Notes also count as acted-on."""
    r = http.get(f"{BASE}/api/stalejobs/followup-status",
                 params={"jobId": job_id, "activityId": activity_id})
    return r.json()


@mcp.tool()
def invoice_by_job(job_id: int) -> dict:
    """Get the QuickBooks invoice number(s) for a given Moraware job id."""
    r = http.post(f"{BASE}/api/checkbot/invoice-by-job", json={"jobId": job_id})
    return r.json()


@mcp.tool()
def job_by_invoice(invoice_number: str) -> dict:
    """Find the Moraware job that carries a given QuickBooks invoice number."""
    r = http.post(f"{BASE}/api/checkbot/job-by-invoice",
                  json={"invoiceNumber": invoice_number})
    return r.json()


@mcp.tool()
def activity_types() -> dict:
    """List all Moraware activity type IDs and their names (e.g. 17 = Follow Up,
    10 = Quote, 4 = Install). Use this when you need to translate a type id to a name."""
    r = http.get(f"{BASE}/api/checkbot/activity-types")
    return r.json()


@mcp.tool()
def cache_status() -> dict:
    """Check EMGBridge cache health: record count, last refresh time, and whether the
    last refresh succeeded. Use this to confirm the backend is up and the data is fresh."""
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
def job_timeline(job_id: int) -> dict:
    """Get the full activity timeline/history for ONE job — every activity in order
    (templates, measures, quotes, installs, follow-ups, etc.) with date, time, type,
    status, assignee, and notes. Use when the user wants a job's history or what's
    happened / what's scheduled on a specific job, e.g. "show me the timeline for [job]"
    or "what's the history on this job?". Pass job_id — resolve the job name first with
    find_job_by_name. READ-ONLY."""
    r = http.get(f"{BASE}/api/scheduler/job-activities", params={"jobId": job_id})
    return r.json()


@mcp.tool()
def assignees() -> dict:
    """List all Moraware crew/assignees with their IDs and active status. Use to look up
    who's in the system, or to resolve a person's name to their ID (e.g. "Mark" → 32)
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
    Reflects the cache (~30 min), so a very recent direct Moraware booking may not appear
    yet. (For ONE job's full history, use job_timeline instead.)"""
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
    X?" (first result) and "how many jobs used X this month?" (count with from_date)."""
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
    InitialBuildComplete is true."""
    r = http.get(f"{BASE}/api/materials/list", params={"limit": limit})
    return r.json()



@mcp.tool()
def jobs_by_salesperson(salesperson: str, natural_stone: bool = False, materials: str = "", installed_before: str = "", installed_after: str = "", limit: int = 200) -> dict:
    """Find jobs by SALESPERSON combined with material and install-date filters — the
    power query for lists like "Alex's natural-stone jobs due for resealing" or
    "Dana's quartzite jobs from the last 6 months". salesperson is a case-insensitive
    name match (e.g. "alex" finds "Alex Sorokin"). Set natural_stone=True to match ALL
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
    for completeness."""
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
    one comes back."""
    digits = "".join(c for c in phone if c.isdigit())
    r = http.post(f"{BASE}/api/lookup/by-phone",
                  json={"lastFourDigits": digits[-4:]})
    return r.json()


from mcp.server.transport_security import TransportSecuritySettings

if __name__ == "__main__":
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = 8000
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["mcp.example.com", "mcp.example.com:*"],
        allowed_origins=["https://mcp.example.com", "https://mcp.example.com:*"],
    )
    mcp.run(transport="streamable-http")
