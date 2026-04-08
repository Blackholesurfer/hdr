# photon

Design Specification

BlackHoleSurfer CMDB — internal technical reference
↓ Download .md
BlackHoleSurfer CMDB — Design Specification
Version History
Version	Date	Description
1.0	2025	Initial CMDB launch
1.5	2026-03	REST API, Incidents, Graph View, Cost Dashboard, Payroll/W-2, AI Chat, Person CIs, Product Catalog
1.6	2026-03-30	Public product analysis (no login), left sidebar nav, recently analyzed, pq.php API pattern, list/search improvements
1.7	2026-03-30	Normalization engine (normalize.php, normalize-ci.php), manufacturer catalog (manufacturer_catalog table), norm status badges on CI pages and graph
Version 1.5 — Feature Set
Architecture

    Stack: PHP 8.0.5, MySQLi, MySQL, shared hosting (blackholesurfer.com)
    Auth: Session-based ($_SESSION['user_id'], role, company_id, company, company_logo)
    Scope pattern: scope.php → get_scope() returns SQL fragment scoping queries to the user's company. Employees see own CIs; managers/owners see all company CIs.
    Roles: employee < manager < owner < superadmin
    Error handling: Global set_exception_handler() + register_shutdown_function() in config.php — shows friendly retry page instead of ISE
    DB: mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT) — all DB errors throw exceptions

Database Tables
users
Column	Type	Notes
id	int PK	
username	varchar	
password	varchar	hashed
role	enum	employee, manager, owner, superadmin
company_id	int FK	→ companies
email	varchar	
companies
Column	Type	Notes
id	int PK	
name	varchar	
logo	varchar	path to logo image
ein	varchar(20)	Employer Identification Number
cmdb_ci
Column	Type	Notes
id	int PK	
user_id	int FK	→ users
token_id	varchar	permanent BHS token (bhs-xxxx)
name	varchar	
ci_type	varchar	see CI Types below
details	text	
serial_number	varchar	hardware types only
cost	decimal	
cost_type	enum	hourly, monthly, One Time Subscription
phone	varchar(30)	person/contact only
email	varchar(150)	person/contact only
linkedin_url	varchar(300)	person/contact only
zip_code	varchar(20)	person/contact — shows Google Maps link
product_id	int FK	→ product_catalog
created_at	timestamp	
updated_at	timestamp	
cmdb_rel
Column	Type	Notes
id	int PK	
source_id	int FK	→ cmdb_ci
target_id	int FK	→ cmdb_ci
rel_type	varchar	e.g. "depends on", "hosts", "manages"
cmdb_incident
Column	Type	Notes
id	int PK	
incident_id	varchar	human-readable ID (e.g. INC-0001)
title	varchar	
severity	enum	P1-Critical, P2-High, P3-Medium, P4-Low
status	enum	Open, In Progress, Resolved, Closed
description	text	
assigned_to	int FK	→ users
created_by	int FK	→ users
created_at	timestamp	
cmdb_incident_ci
Column	Type	Notes
incident_id	int FK	→ cmdb_incident
ci_id	int FK	→ cmdb_ci
api_keys
Column	Type	Notes
id	int PK	
user_id	int FK	→ users
label	varchar	friendly name
key_hash	varchar(64)	SHA-256 of raw key
active	tinyint	1 = active
created_at	timestamp	
last_used	timestamp	
manufacturer_catalog
Column	Type	Notes
id	int PK	
company_id	int FK	→ companies (tenant scoping)
name	varchar(150)	full legal name
duns_number	varchar(20)	Dun & Bradstreet unique identifier
address	varchar(255)	
city	varchar(100)	
state	varchar(100)	
country	varchar(100)	
website	varchar(300)	
notes	text	
created_at	datetime	
updated_at	timestamp	ON UPDATE CURRENT_TIMESTAMP

Modeled on BMC's COM:Company table — separates manufacturer identity and contact details from product data. Products reference this table via manufacturer_id FK. Updating the manufacturer name in this table syncs the denormalized manufacturer text field across all linked products.
product_catalog
Column	Type	Notes
id	int PK	
company_id	int FK	→ companies
bhs_product_id	varchar(40)	permanent BHS public ID (bhsp-xxxx)
category	varchar(80)	user-defined classification, used with Type + Item
type	varchar(80)	user-defined classification, used with Category + Item
item	varchar(150)	user-defined sub-categorization, used with Category + Type
model	varchar(150)	name by which the product is generally known (e.g. Pro Widget 2000)
manufacturer_id	int FK	→ manufacturer_catalog
manufacturer	varchar(150)	denormalized copy of manufacturer name for query convenience
version	varchar(80)	version number of the entity
patch_number	varchar(80)	
product_url	varchar(300)	
linkedin_url	varchar(300)	
notes	text	
normalization_status	int	see Normalization Status Codes below
canonical_category	varchar(80)	approved canonical value
canonical_type	varchar(80)	approved canonical value
canonical_manufacturer	varchar(150)	approved canonical value
canonical_item	varchar(150)	approved canonical value
canonical_model	varchar(150)	approved canonical value
canonical_version	varchar(80)	approved canonical value
created_at	datetime	
updated_at	timestamp	
product_requests
Column	Type	Notes
id	int PK	
product_id	int FK	→ product_catalog
company_id	int FK	→ companies
request_type	enum	upgrade, alternative, migration
summary	varchar(300)	one-line AI summary
details	text	full AI recommendation
assigned_to	int FK	→ users (manager assigns to staff)
status	enum	open, in_progress, accepted, dismissed
created_at	timestamp	
updated_at	timestamp	
product_request_cis
Column	Type	Notes
request_id	int FK	→ product_requests
ci_id	int FK	→ cmdb_ci
CI Types

server, mainframe, workstation, laptop, virtual_machine, cluster, storage_device, printer, application, web_app, mobile_app, desktop_app, os, middleware, app_server, web_server, message_queue, software_license, database, service, cloud_service, iaas, paas, saas, container, router, switch, firewall, load_balancer, wireless_ap, ip_network, vlan, vpn, ip_address, network_iface, network_device, san, nas, tape_library, person, contact, other

Special rendering:

    Hardware types (server, workstation, laptop, etc.): show serial number field
    Person/Contact types: show phone, email, LinkedIn URL, zip code (Google Maps link)

Pages
File	Role Access	Description
login.php	public	Login form + public product analysis widget
logout.php	any	Session destroy
cmdb-home.php	any	Dashboard / home
graph.php	any	vis.js impact graph
graph-data.php	any	JSON API for graph data
list-ci.php	any	CI list with search/filter/sort
add-ci.php	any	Add new CI
edit-ci.php	any	Edit CI (scoped)
list-rel.php	any	Relationship list
add-rel.php	any	Add relationship (with search/sort)
list-incidents.php	any	Incident list, sortable
view-incident.php	any	View/update incident
add-incident.php	any	Create incident
cost-dashboard.php	any	Cost breakdown (sortable columns)
import.php	any	CSV/Excel CI import
tools.php	any	Utilities
api-keys.php	any	Manage REST API keys
w2.php	any	W-2 viewer (employees: own only; managers: all)
payroll-setup.php	manager/owner	Payroll setup
payroll-run.php	manager/owner	Run payroll
company-view.php	manager/owner	Team management, invite members
subscription.php	manager/owner	Subscription management
product-catalog.php	any (edit: manager/owner)	Product catalog list
add-product.php	manager/owner	Add product to catalog
edit-product.php	manager/owner	Edit catalog product + linked CI normalization status
product-analysis.php	any (assign: manager/owner)	AI analysis + request management
manufacturers.php	manager/owner	Manufacturer catalog list
edit-manufacturer.php	manager/owner	Add/edit manufacturer (DUNS, address, etc.)
normalize.php	manager/owner	Normalization engine — clusters, pending approval, unnormalized CIs
normalize-ci.php	manager/owner	Per-CI normalization — link product, approve canonical values, create new product
admin.php	superadmin	System administration
REST API (/api/)

Base path: /impact/api/ Auth: X-API-Key: <key> header
Endpoint	Methods	Description
ci.php	GET, POST, PUT, DELETE	CI management. Filters: ?type=, ?search=
incidents.php	GET, POST, PUT	Incident management. Filters: ?status=, ?severity=
relationships.php	GET, POST, DELETE	Relationships. Filter: ?ci_id=
chat.php	POST	AI support chat (Claude Haiku). Body: {message, history[]}
Authentication

Generate an API key from Settings → API Keys in the portal. Pass it as a request header on every call:

X-API-Key: YOUR_API_KEY_HERE

All responses are JSON. Successful list responses return {count, data[]}. Errors return {error: "message"} with an appropriate HTTP status code.
Field reference — CI (ci.php)
Field	Type	Required	Notes
name	string	POST	Display name
ci_type	string	POST	One of: person, service, app, server, db, laptop, network, contact
details	string	—	Free-text description
serial_number	string	—	Hardware types
cost	decimal	—	Numeric value
cost_type	string	—	hourly, monthly, or One Time Subscription
Field reference — Incidents (incidents.php)
Field	Type	Required	Notes
title	string	POST	Short description
description	string	—	Full detail
severity	string	—	P1-Critical, P2-High, P3-Medium, P4-Low (default: P3-Medium)
assigned_to	string	—	Username to assign
ci_ids	int[]	—	Array of CI IDs to link
expected_fix_date	string	—	ISO date YYYY-MM-DD
status	string	PUT only	Open, In Progress, Resolved, Closed
Field reference — Relationships (relationships.php)
Field	Type	Required	Notes
source_id	int	POST	CI ID
target_id	int	POST	CI ID (must differ from source)
rel_type	string	POST	e.g. depends on, hosts, manages
Python — Discovery & Common Operations

import requests

BASE = "https://www.blackholesurfer.com/impact/api"
KEY  = "YOUR_API_KEY_HERE"
HDR  = {"X-API-Key": KEY, "Content-Type": "application/json"}

# List all CIs
r = requests.get(f"{BASE}/ci.php", headers=HDR)
cis = r.json()
print(f"{cis['count']} CIs found")
for ci in cis['data']:
    print(f"  [{ci['id']}] {ci['name']} ({ci['ci_type']})")

# Filter by type
r = requests.get(f"{BASE}/ci.php", headers=HDR, params={"type": "server"})
servers = r.json()['data']

# Search by name/details
r = requests.get(f"{BASE}/ci.php", headers=HDR, params={"search": "web"})
results = r.json()['data']

# Get a single CI with relationships and linked incidents
r = requests.get(f"{BASE}/ci.php", headers=HDR, params={"id": 42})
ci = r.json()
print(ci['relationships'])
print(ci['incidents'])

# Create a CI
r = requests.post(f"{BASE}/ci.php", headers=HDR, json={
    "name": "prod-web-01",
    "ci_type": "server",
    "details": "Primary web server",
    "cost": 120.00,
    "cost_type": "monthly"
})
new_id = r.json()['id']

# Update a CI
requests.put(f"{BASE}/ci.php?id={new_id}", headers=HDR, json={
    "details": "Primary web server — upgraded to 64GB RAM"
})

# Delete a CI
requests.delete(f"{BASE}/ci.php?id={new_id}", headers=HDR)

# Create an incident linked to CIs
r = requests.post(f"{BASE}/incidents.php", headers=HDR, json={
    "title": "prod-web-01 unreachable",
    "description": "Health check failing since 02:00 UTC",
    "severity": "P1-Critical",
    "ci_ids": [42, 17]
})
inc_id = r.json()['id']

# Resolve the incident
requests.put(f"{BASE}/incidents.php?id={inc_id}", headers=HDR, json={
    "status": "Resolved"
})

# List open P1 incidents
r = requests.get(f"{BASE}/incidents.php", headers=HDR,
                 params={"status": "Open", "severity": "P1-Critical"})
print(r.json()['data'])

# Create a relationship
requests.post(f"{BASE}/relationships.php", headers=HDR, json={
    "source_id": 42,
    "target_id": 17,
    "rel_type": "depends on"
})

# Get all relationships for a CI
r = requests.get(f"{BASE}/relationships.php", headers=HDR, params={"ci_id": 42})
print(r.json()['data'])

PowerShell — Discovery & Common Operations

$BASE = "https://www.blackholesurfer.com/impact/api"
$HDR  = @{ "X-API-Key" = "YOUR_API_KEY_HERE"; "Content-Type" = "application/json" }

# List all CIs
$r   = Invoke-RestMethod "$BASE/ci.php" -Headers $HDR
Write-Host "$($r.count) CIs found"
$r.data | ForEach-Object { Write-Host "  [$($_.id)] $($_.name) ($($_.ci_type))" }

# Filter by type
$servers = (Invoke-RestMethod "$BASE/ci.php?type=server" -Headers $HDR).data

# Search
$results = (Invoke-RestMethod "$BASE/ci.php?search=web" -Headers $HDR).data

# Get a single CI
$ci = Invoke-RestMethod "$BASE/ci.php?id=42" -Headers $HDR
$ci.relationships
$ci.incidents

# Create a CI
$body  = @{ name="prod-web-01"; ci_type="server"; details="Primary web server"; cost=120; cost_type="monthly" } | ConvertTo-Json
$newCI = Invoke-RestMethod "$BASE/ci.php" -Method POST -Headers $HDR -Body $body
$newId = $newCI.id

# Update a CI
$body = @{ details="Primary web server — upgraded to 64GB RAM" } | ConvertTo-Json
Invoke-RestMethod "$BASE/ci.php?id=$newId" -Method PUT -Headers $HDR -Body $body

# Delete a CI
Invoke-RestMethod "$BASE/ci.php?id=$newId" -Method DELETE -Headers $HDR

# Create an incident
$body = @{
    title       = "prod-web-01 unreachable"
    description = "Health check failing since 02:00 UTC"
    severity    = "P1-Critical"
    ci_ids      = @(42, 17)
} | ConvertTo-Json
$inc   = Invoke-RestMethod "$BASE/incidents.php" -Method POST -Headers $HDR -Body $body
$incId = $inc.id

# Resolve the incident
$body = @{ status = "Resolved" } | ConvertTo-Json
Invoke-RestMethod "$BASE/incidents.php?id=$incId" -Method PUT -Headers $HDR -Body $body

# List open P1s
$open = Invoke-RestMethod "$BASE/incidents.php?status=Open&severity=P1-Critical" -Headers $HDR
$open.data

# Create a relationship
$body = @{ source_id=42; target_id=17; rel_type="depends on" } | ConvertTo-Json
Invoke-RestMethod "$BASE/relationships.php" -Method POST -Headers $HDR -Body $body

# Get relationships for a CI
(Invoke-RestMethod "$BASE/relationships.php?ci_id=42" -Headers $HDR).data

AI Features
Support Chat Widget (footer.php + api/chat.php)

    Floating bubble on every page (bottom-right)
    Powered by Claude Haiku (claude-haiku-4-5-20251001)
    System prompt is role-aware: tailors answers based on $_SESSION['role']
    Conversation history persists across page navigation via sessionStorage
    Resizable panel, text-selectable messages
    Config: $anthropic_api_key in config.php

Product AI Analysis (product-analysis.php)

    Triggered per product via "Run AI Analysis" button
    Sends product details (manufacturer, item, model, version, patch, CI count) to Claude Haiku
    Returns structured JSON with three recommendation types:

- Upgrade — is a newer version/patch available? - Alternative — cheaper or better competing products? - Migration — technology replacement path?

    Results saved as product_requests records
    Affected CIs automatically linked via product_request_cis
    Managers/owners can assign requests to staff and update status

Navigation

All authenticated pages include header.php which renders a left vertical sidebar (200px wide). Page content uses margin-left: 200px to accommodate it.

Sidebar sections and role gating:

    CMDB — CIs, Relationships, Graph, Incidents (all roles)
    Financials — Cost Dashboard, Payroll, W-2 (Payroll: manager/owner only)
    Settings — Company View, Product Catalog, Subscription, API Keys (Company View + Subscription: manager/owner only)
    Admin — superadmin only

Version 1.6 — Completed 2026-03-30
Public Product Analysis (login.php + pq.php)

No account required. Visitors to login.php can analyze any product using Claude Haiku.

UI layout (login.php):

    Two-column grid: left column = login form; right column = product analysis widget
    Cascading dropdowns: Manufacturer → Item → Model → Version (populated from product_catalog, LIMIT 300 per level to prevent memory spikes)
    After analysis, results display inline with expandable sections (upgrade, alternative, migration, overall risk)
    Recently Analyzed sidebar below results shows last 15 analyses from all users; auto-refreshes after each successful analysis

Rate limiting:

    5 analyses per IP per hour
    500 analyses per day (global across all users)
    Tracked in public_analysis_log

API endpoint (pq.php):

    GET-only — avoids mod_security WAF blocks that affect POST to new files on shared cPanel hosting
    Parameters: ?a=manufacturer&b=item&c=model&d=version&e=patch_number&f=bhs_product_id
    Short single-letter param names avoid mod_security keyword filters
    Returns JSON: {ok, id, result: {upgrade, alternative, migration, overall_risk, overall_notes}, product}
    login.php fetches pq.php via fetch() with URLSearchParams

Recently Analyzed fragment (login.php?sidebar=1):

    Returns an HTML fragment (no full page) listing recent analyses
    Called via fetch('login.php?sidebar=1') after each analysis to refresh the sidebar
    Renders expandable rows with manufacturer, item, model, overall risk badge

public_analysis_log table
Column	Type	Notes
id	int PK	
ip	varchar(45)	client IP (IPv6-safe)
manufacturer	varchar(150)	
item	varchar(150)	
model	varchar(150)	
version	varchar(80)	
bhs_product_id	varchar(40)	
result_json	text	full Claude JSON response
created_at	timestamp	
UI Improvements

    Sorting and search on list-ci.php — column header clicks toggle ASC/DESC; search box filters by name/type/details
    Sorting and search on add-rel.php — find CIs quickly when building relationships
    Cost dashboard sortable columns — Name, Company, Type, Cost, Monthly

Version 1.7 — Completed 2026-03-30
Normalization Engine

Modeled on the BMC ADDM normalization approach. Tracks data quality across six fields of product_catalog using a 7-level status code system. Accessible to manager/owner/superadmin only.
Field Definitions (BMC-aligned)
Field	BMC Definition
Category	User-defined categorization of the instance, used with Type and Item
Type	User-defined categorization of the instance, used with Category and Item
Item	User-defined sub-categorization of the instance, used with Category and Type
Manufacturer	Organization that produced the entity (maps to manufacturer_catalog)
Model	Name by which the entity is generally known (e.g. "Pro Widget 2000")
Version	Version number of the physical entity
Normalization Status Codes
Code	Label	Color
10	Other	grey
20	Not Normalized	grey
30	Not Applicable for Normalization	dark grey
40	Normalization Failed	red
50	Normalized but Not Approved	yellow
60	Normalized and Approved	green
70	Modified after last Normalization	orange

Status is stored in product_catalog.normalization_status. CIs link to products via cmdb_ci.product_id; normalization status surfaces on CI pages via LEFT JOIN.
Eligible CI Types

All CI types are eligible for normalization except: person, contact, ip_network, vlan, vpn, ip_address, network_iface, other. The Normalize button and normalize-ci.php enforce this at the UI and request level.
Field Hierarchy and Fuzzy Clustering (normalize.php)

Fields are scoped hierarchically — each field's cluster is scoped within the canonical values of all parent fields:

Category → Type → Manufacturer → Item → Model → Version

Fuzzy matching uses fuzzy_key(): strips legal suffixes (inc, corp, ltd, llc, gmbh, etc.) and non-alphanumeric characters, lowercases. Products with 2+ distinct spellings that fuzzy-match are grouped into a conflict cluster.

Scan logic (run_scan POST action):

    Status 70 (Modified): product was previously approved (60) but a field value no longer matches its canonical value
    Status 40 (Failed): product belongs to a multi-variant cluster and has not been resolved

Tabs on normalize.php:

    Clusters — field selector pills (Category/Type/Manufacturer/Item/Model/Version); each cluster shows all spellings + a canonical input pre-filled with the most common spelling; Apply button sets status=50 for all cluster members
    Pending Approval — checkbox table of status=50 records; Approve (→60) or Dismiss (→30) in bulk
    Failed / Modified — status 40 and 70 records
    All Records — full table with data-status attribute; clicking a status overview card filters this tab
    Unnormalized CIs — eligible CIs where product_id IS NULL or linked product status ≠ 60; each row has a direct Normalize → link to normalize-ci.php

Per-CI Normalization (normalize-ci.php)

Takes ?ci_id=X&back=list|edit. Three paths:

1. No product linked — dropdown to select an existing product from product_catalog, or expand "Create a new product" form to insert a new product_catalog entry at status=60 and link the CI in one step 2. Product linked, not approved — review/edit canonical field values and approve (status=60); manufacturer and item fields sync to canonical values on approval 3. Product linked, already approved — read-only status display

bhs_product_id generated as bhsp- + 8 random alphanumeric characters.

CI type → suggested Category/Type pre-fills via $type_map array (e.g. os → ['Software', 'Operating System']).
Normalization Status in the UI

    list-ci.php — norm status badge rendered next to CI type pill; Normalize button shown for eligible types (bold when not approved, subtle when approved)
    edit-ci.php — norm status badge below product catalog dropdown with "→ Normalize this CI" link when not status 60
    graph.php — normalization status filter dropdown in controls bar; norm badge shown in node info panel; graph-data.php includes norm_status in node data

Manufacturer Catalog

Separates manufacturer identity from product data, modeled on BMC's COM:Company table.

manufacturer_catalog stores: name, D-U-N-S number (Dun & Bradstreet), address, city, state, country, website, notes — all per-tenant (company_id).

product_catalog gains:

    manufacturer_id INT FK → manufacturer_catalog
    manufacturer VARCHAR — denormalized copy kept in sync; allows normalization queries to work without joins

Migration: distinct manufacturer text values from product_catalog are auto-imported into manufacturer_catalog on first setup; products linked via UPDATE ... JOIN.

Pages:

    manufacturers.php — list with product count badges (linked to filtered product catalog), DUNS, location, website
    edit-manufacturer.php — add/edit form; saving a name change propagates to all linked product_catalog.manufacturer text fields; shows linked products table at bottom

add-product.php / edit-product.php: manufacturer free-text input replaced with <select> populated from manufacturer_catalog, with "+ Add new" link opening edit-manufacturer.php.

edit-product.php also shows a Linked CIs section at the bottom — table of all CIs with product_id = this product, showing normalization status badge and a Normalize → link for any not at status 60.
Technical Notes & Gotchas
config.php exception handler

config.php sets both mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT) and a global set_exception_handler() that returns an HTML "Temporary Error" page for any uncaught exception. The handler checks $_SERVER['REQUEST_URI'] for /api/ to decide between HTML and JSON responses, but this only covers the /api/ path.

Rule: Any new JSON endpoint outside /api/ (e.g., pq.php) MUST: 1. Override the exception handler immediately after require_once config.php: ```php set_exception_handler(function(\Throwable $e) { if (!headers_sent()) header('Content-Type: application/json'); echo json_encode(['error' => 'Service temporarily unavailable.']); exit; }); ``` 2. Call mysqli_report(MYSQLI_REPORT_OFF) and check connection/query results manually.

Failing to do this causes DB errors (even transient ones) to return an HTML page instead of JSON, which breaks any JS fetch() caller expecting JSON.
mod_security on shared cPanel hosting

The WAF on this host blocks:

    POST requests to newly created PHP files (even with valid content)
    GET/POST requests with base64-encoded query string values (?q=base64data)
    POST body containing certain IT-related field names (manufacturer, version, patch_number, etc.) on auth pages

Pattern for public API endpoints: Use GET with short single-letter parameter names (?a=...&b=...). This bypasses all known WAF rules without needing to modify .htaccess.
Product catalog query size

Querying product_catalog without a LIMIT can load thousands of rows into PHP memory, causing an OOM kill that manifests as a "Temporary Error" page (the same HTML as the exception handler, making it hard to distinguish). Always apply LIMIT 300 on catalog queries used to populate UI dropdowns.
Future Roadmap

    Year-aware cost reports — year selector, monthly totals per year, historical snapshots
    Payroll history — multi-year pay period records
    Public Product Registry — bhs_product_id (bhsp-xxxx) as permanent public identifiers; manufacturers claim listings; companies subscribe to manufacturer feeds
    Change management / RFC workflow
    SLA tracking on incidents
    Automated vulnerability feed integration (CVE matching against product versions)
    Mobile app
    Multi-region / multi-site CI grouping

