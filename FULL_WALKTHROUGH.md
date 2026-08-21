# Full Build Walkthrough — Enterprise Text-to-SQL Agent

This document is a complete, phase-by-phase record of how this project was built,
starting from a blank Windows machine. It includes every tool installed, every
script written, every real error hit along the way, and how each was fixed. It's
written so the whole project can be reproduced end to end without any other
reference.

**Stack summary:** Windows, Python 3.12, PostgreSQL, Neo4j Desktop (Enterprise,
with `neosemantics` + `APOC`), Protégé (ontology editor), VS Code, Git, DBeaver,
OpenAI GPT-4o, Streamlit.

---

## Phase 0 — Environment Setup

### 0.1 Install core tools (in order)

1. **Python 3.10+** — python.org/downloads. On the installer's first screen,
   check **"Add python.exe to PATH"** before clicking Install — this is the
   single most common setup failure if skipped. Verify: `python --version`,
   `pip --version`.
2. **PostgreSQL** (16 or 17) — via the EDB installer (postgresql.org/download/windows).
   Record the postgres superuser password set during install — needed constantly
   afterward. Verify by opening **SQL Shell (psql)** from the Start Menu and
   connecting with defaults.
3. **Git** — git-scm.com/download/win. Defaults are correct for every screen.
   Verify: `git --version`.
4. **VS Code** — code.visualstudio.com. During install, keep **"Add to PATH"**
   checked. After install, add the **Python extension** (Ctrl+Shift+X, search
   "Python", install Microsoft's). Verify: `code --version`.
5. **Neo4j Desktop** — neo4j.com/download. Requires a free account/login to
   activate. Don't create a database yet — that happens in Phase 3.
6. **DBeaver** (Community Edition) — dbeaver.io/download. Used to inspect
   Postgres visually throughout the project.

### 0.2 Project folder structure

```powershell
cd C:\Users\<you>
mkdir text2sql-kg-project
cd text2sql-kg-project
mkdir config, data\raw, data\bronze, data\silver, data\gold, sql\ddl, sql\dq_checks, `
      ontology, src\generation, src\ingestion, src\kg, src\agent, src\utils, `
      notebooks, tests\eval, docs
code .
```

### 0.3 Python virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
If PowerShell blocks script execution: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`,
confirm with `Y`, then retry activation. You must re-activate every time you
open a new terminal (`(venv)` prefix confirms it's active).

### 0.4 Secrets and version control

- `.gitignore`: `venv/`, `.env`, `__pycache__/`, `*.pyc`, `.vscode/`, `data/raw/*.csv`, `*.log`
- `.env.template` (committed, no real values) and `.env` (real values, gitignored):
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=enterprise_lakehouse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
OPENAI_API_KEY=
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=
```
- `git init`, then `git status` and confirm `.env` does **not** appear in
  untracked files (proves `.gitignore` is working before any secret is committed).

### 0.5 Base Python packages

`requirements.txt`:
```
faker==24.4.0
psycopg2-binary==2.9.9
sqlalchemy==2.0.29
pandas==2.2.1
python-dotenv==1.0.1
pyyaml==6.0.1
```
```powershell
pip install -r requirements.txt
```

---

## Phase 1 — The Lakehouse Data Layer (Postgres)

**Goal:** realistic, intentionally messy enterprise data — not a clean toy CSV —
run through a proper bronze → silver → gold pipeline.

### 1.1 Create the database and schemas (via DBeaver)

Connect DBeaver to Postgres (host `localhost`, port `5432`, user `postgres`),
then in a SQL editor:
```sql
CREATE DATABASE enterprise_lakehouse;
-- reconnect DBeaver's connection to point at enterprise_lakehouse, then:
CREATE SCHEMA bronze;
CREATE SCHEMA silver;
CREATE SCHEMA gold;
```

### 1.2 Bronze DDL (`sql/ddl/bronze.sql`)

Loose typing (`TEXT` columns everywhere) plus lineage columns
(`_source_file`, `_loaded_at`) — mirrors how raw data actually lands before
cleaning. Six tables: `customers`, `products`, `suppliers`, `stores`, `orders`,
`order_items`.

### 1.3 Synthetic data generator (`src/generation/generate_data.py`)

Uses `Faker` (seeded: `Faker.seed(42)`, `random.seed(42)` for reproducibility)
to generate:
- 5,000 customers (+ ~2% intentional duplicates → 5,100 rows), ~1% missing emails,
  dates in three different formats (`YYYY-MM-DD`, `MM/DD/YYYY`, `DD-Mon-YYYY`)
- 500 products across 4 categories × 3 subcategories each
- 60 suppliers, 25 stores (Online + Physical Store channels)
- 50,000 orders over a 2-year span, 1-5 line items each (~150,000 line items)

Run: `python src\generation\generate_data.py` → writes CSVs to `data/raw/`.

### 1.4 Load bronze (`src/ingestion/load_bronze.py`)

Reads each CSV with `pandas`, tags rows with `_source_file`, and appends into
the matching `bronze.*` table via SQLAlchemy. Run:
`python -m src.ingestion.load_bronze`.

### 1.5 Silver DDL + transform (`sql/ddl/silver.sql`, `src/ingestion/transform_silver.py`)

Proper types (`DATE`, `NUMERIC`, `INTEGER`, `BOOLEAN`), primary keys, foreign
keys. The transform script:
- Deduplicates customers by `customer_id` (removes the ~2% injected duplicates)
- Parses the three mixed date formats into real `DATE` values
  (`pd.to_datetime(..., format="mixed")`)
- Flags missing emails (`is_email_missing`)
- Drops any rows with orphaned foreign keys (defensive, though the synthetic
  data has none by construction)

Run: `python -m src.ingestion.transform_silver`.

### 1.6 Gold DDL + transform (`sql/ddl/gold.sql`, `src/ingestion/transform_gold.py`)

A proper star schema: `dim_customer`, `dim_product`, `dim_supplier`, `dim_store`,
`dim_date` (surrogate keys, `SERIAL`), and `fact_orders` (one row per order
line item, foreign keys to every dimension, plus derived `line_revenue` and
`margin_pct`). Run: `python -m src.ingestion.transform_gold`.

**Sanity check** (in DBeaver): total revenue by category should return exactly
4 rows (Electronics, Apparel, Home, Grocery) with sensible numbers.

---

## Phase 2 — The Ontology (OWL + SKOS, in Protégé)

**Goal:** formally define what business terms *mean*, not just what columns
are called — this is the layer a plain schema-only agent has no access to.

### 2.1 Install and open Protégé

protege.stanford.edu/software.php → download → run installer (defaults) or
extract the zip and run `run.bat`. On first launch, dismiss the "Automatic
Update" plugin popup ("Not now").

### 2.2 Create the ontology

`File → New Empty Ontology` → IRI: `http://enterprise-lakehouse.org/ontology`
→ `File → Save As...` → save into `ontology\owl\enterprise_ontology.owl` as
**RDF/XML**.

### 2.3 Classes (Entities → Classes)

Six core classes under `owl:Thing`, each selected → "Add subclass" icon:
`Customer`, `Order`, `OrderLineItem`, `Product`, `Supplier`, `Store` — each
given an `rdfs:comment` business definition (e.g., Customer: *"An individual
or organization that has placed one or more orders in the enterprise
system."*).

### 2.4 Taxonomy (subclassing)

Under `Product`: `Electronics`, `Apparel`, `Home`, `Grocery`, each with 3
subclasses (e.g. Electronics → `Laptops`, `Phones`, `Accessories`). Under
`Customer`: `EnterpriseCustomer`, `SMBCustomer`, `ConsumerCustomer`.

### 2.5 SKOS labeling

`Active ontology → Ontology imports → Direct Imports → +` → "Import an
ontology contained in a document located on the web" →
`http://www.w3.org/2004/02/skos/core`. Once imported, each class gets a
`skos:prefLabel` annotation (appears in Protégé's picker as **"preferred
label"**, nested under `rdfs:label` — this is the same property, just shown
by its display name rather than its prefixed ID).

> **Note on `skos:broader`:** we deliberately did *not* also add
> `skos:broader` annotations, because it's an OWL *object property* (a
> relationship between individuals), not usable as a class annotation — the
> OWL `subClassOf` hierarchy from step 2.4 already captures the same taxonomy
> structurally, so duplicating it wasn't worth the added complexity.

### 2.6 Object properties (relationships)

`Entities → Object properties`, six under `owl:topObjectProperty`:
`placesOrder` (Customer→Order), `hasLineItem` (Order→OrderLineItem),
`forProduct` (OrderLineItem→Product), `suppliedBy` (Product→Supplier),
`fulfilledByStore` (Order→Store), `belongsToCategory` (Product→Product). Each
gets a **Domain** and **Range** set via the `+` icons in their respective
panels.

### 2.7 Data properties (attributes)

Ten under `owl:topDataProperty`: `hasCustomerId`, `hasSignupDate`,
`hasChurnStatus`, `hasOrderDate`, `hasOrderStatus`, `hasQuantity`,
`hasUnitPrice`, `hasUnitCost`, `hasMarginPct`, `hasLineRevenue` — each with a
Domain (class) and Range (XSD datatype: `xsd:string`, `xsd:dateTime` — plain
`xsd:date` wasn't available in this Protégé build's datatype picker, so
`xsd:dateTime` was used instead, formatted with a midnight time component when
loading real dates later).

### 2.8 The key logical restriction

On `EnterpriseCustomer` (and mirrored on `SMBCustomer`, `ConsumerCustomer`):
`Description → SubClass Of → +`, typed directly as a class expression:
```
Customer and (hasChurnStatus value "Active")
```
This is the formal, machine-reasoned definition of what "active
[segment] customer" means — the single most important artifact this ontology
produces, since it's exactly the ambiguity a schema-only Text-to-SQL agent
gets wrong (see Phase 5 results).

### 2.9 Validate with the reasoner

`Reasoner` menu → select **HermiT** → `Start reasoner`. Check the bottom
status bar for the active reasoner name and confirm no red inconsistency
icons appear on any class.

---

## Phase 3 — Knowledge Graph (Neo4j)

**Goal:** turn the ontology into real graph data, then load the actual
gold-layer business records on top of it, connected via the same
relationships defined in the ontology.

### 3.1 Create the Neo4j instance

Neo4j Desktop → Local instances → **Create instance** → name it, set a
password, **pick version 5.26.0 explicitly** (see 3.2 for why) → Create → Start.

> **Version note:** the default/latest Neo4j Desktop version (2026.06.0 /
> 2026.07.0 in this build) is newer than what the `neosemantics` plugin
> currently supports (latest release targets 5.26.0). Using the latest
> version caused a hard startup crash (`ComponentInjectionException:
> ... apoc.Pools ... not a known injectable component`) once neosemantics'
> JAR was manually dropped into the plugins folder. Creating a second
> instance pinned to **5.26.0** resolved this — the original newer instance
> was left alone, unused, for this project.

### 3.2 Install neosemantics (manual JAR install)

Neo4j Desktop's built-in plugin catalog didn't list `neosemantics` for this
Desktop version, so it was installed manually:
1. Stop the instance.
2. Download `neosemantics-5.26.0.jar` from
   `github.com/neo4j-labs/neosemantics/releases` (matching the instance's
   Neo4j version exactly).
3. Instance's `...` menu → Open folder → **Plugins** → drop the JAR in.
4. Instance's `...` menu → Open folder → **Configuration** → edit
   `neo4j.conf`, add:
   ```
   dbms.security.procedures.unrestricted=n10s.*,apoc.*
   dbms.security.procedures.allowlist=n10s.*,apoc.*
   ```
5. Start the instance again.
6. Verify (Neo4j Desktop → instance → Query, or Neo4j Browser):
   ```cypher
   SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'n10s' RETURN name LIMIT 5;
   ```
   (Note: the older `CALL dbms.procedures()` syntax has been replaced by
   `SHOW PROCEDURES` in current Cypher — the old syntax throws a
   confusing "no such procedure" error that looks like a missing-plugin
   problem but isn't.)

### 3.3 Initialize n10s and add the uniqueness constraint

```cypher
CALL n10s.graphconfig.init();
CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE;
```

### 3.4 Import the ontology (`src/kg/import_ontology.py`)

Connects via the `neo4j` Python driver and calls:
```cypher
CALL n10s.onto.import.fetch($file_uri, "RDF/XML")
```
against the local `enterprise_ontology.owl` file (as a `file:///...` URI). This
loads your Protégé classes/properties as real graph nodes, labeled
`n4sch__Class`, `n4sch__Property`, `n4sch__Relationship` (the `n4sch__`
prefix is n10s's default naming for imported ontology/schema elements — this
tripped up an early verification query written as `MATCH (c:Class)`, which
returns nothing; the correct label is `n4sch__Class`).

### 3.5 Load the actual business data (`src/kg/load_graph_data.py`)

Reads each `gold.dim_*` / `gold.fact_orders` table from Postgres via pandas,
and `MERGE`s them into Neo4j as real `:Customer`, `:Product`, `:Supplier`,
`:Store`, `:Order`, `:OrderLineItem` nodes, connected via `:placesOrder`,
`:hasLineItem`, `:forProduct`, `:suppliedBy`, `:fulfilledByStore` relationships
— i.e., real instances of the ontology's classes and relationships.
Order-line-item loading is batched (5,000 rows/batch) to keep transactions
manageable at ~150,000 rows. Uniqueness constraints are created first
(`customer_id`, `product_id`, `supplier_id`, `store_id`, `order_id`) so `MERGE`
is idempotent on reruns.

**Sanity check:**
```cypher
MATCH (c:Customer)-[:placesOrder]->(o:Order)-[:hasLineItem]->(li:OrderLineItem)-[:forProduct]->(p:Product)
RETURN c.full_name, o.order_id, p.product_name, li.quantity, li.line_revenue
LIMIT 10;
```

---

## Phase 4 — The Baseline Text-to-SQL Agent (control group)

`src/agent/baseline_text2sql.py`: dumps the raw `information_schema.columns`
for the `gold` schema (table/column names + types, nothing else) into a
GPT-4o prompt, asks for a single SQL query, executes it against Postgres, and
returns the result. **No** ontology, KG, or business context — deliberately,
to serve as the control group.

Setup note: this was also where the OpenAI API key setup issues were worked
through (see "Troubleshooting log" below) — the account was fully valid the
whole time; the actual blockers were a `proxies` TypeError from a pinned old
`openai` package version, and later a stale system-level `OPENAI_API_KEY`
environment variable shadowing the `.env` file's value.

---

## Phase 5 — The GraphRAG-Powered Agent

### 5.1 Graph retrieval layer (`src/kg/graph_retrieval.py`)

Queries the Neo4j knowledge graph and assembles four sections of context:
1. **Business glossary** — every ontology class + its `rdfs:comment` definition
2. **Category taxonomy** — the `subClassOf` hierarchy (e.g. "Electronics is a
   type of Product")
3. **Entity relationships** — every object property with its Domain → Range,
   giving the agent correct join logic
4. **Business rules** — explicit, hand-surfaced restatements of the OWL
   logical restrictions from Phase 2.8 (e.g. *"EnterpriseCustomer means:
   Customer with segment='Enterprise' AND churn_status='Active'"*), plus a
   handful of additional disambiguation rules added after the first eval run
   (see 5.3) — this function is a stand-in for full automated OWL-restriction
   parsing, which would be the natural next engineering step.

### 5.2 The KG agent (`src/agent/kg_text2sql.py`)

Same shape as the baseline agent, but the prompt additionally includes the
full `build_graph_context()` output, with an explicit instruction to use the
glossary/rules to resolve ambiguous terms and the relationships to determine
correct joins.

**First manual test** (question the baseline got wrong): *"How many active
enterprise customers do we have?"* — baseline generated
`WHERE churn_status = 'active' AND segment = 'enterprise'` (wrong case, matches
nothing); the KG agent generated
`WHERE segment = 'Enterprise' AND churn_status = 'Active'` (correct case, from
the business rules context) and returned **581**.

### 5.3 Debugging real failures (not chasing phantom ones)

Four "hard" questions initially failed on the KG agent's first full run. Each
was diagnosed individually rather than assumed to be agent error:

| # | Question | Root cause | Fix |
|---|---|---|---|
| 6 | Revenue by region | Genuine ambiguity — both `dim_customer.region` and `dim_store.region` exist; agent picked store's | Added an explicit disambiguation rule to graph_retrieval.py |
| 8 | Top 5 products by quantity | **Eval harness bug**, not agent error — agent's SQL was correct but included an extra `product_id` column the comparator flagged as a mismatch | Fixed `results_match()` to compare only overlapping columns |
| 11 | Revenue per customer by segment | Agent filtered to active-only customers, a reasonable but unintended reading | Added a rule clarifying the default scope is all customers |
| 13 | Supplier margin | Agent hallucinated a `supplier_key` column on `gold.dim_product` that doesn't exist — the real join path requires `silver.products` | Added an explicit rule stating the correct join path |

Adding all three new rules at once caused a real (reproducible, not
run-to-run noise) *regression* on two previously-passing questions — isolating
by reverting the rules one at a time confirmed the *original* seven rules
were fine, and the exact interaction wasn't fully pinned down before moving
on; this is flagged here as an open item rather than papered over.

### 5.4 Evaluation harness (`tests/eval/eval_questions.py`, `run_eval.py`)

15 hand-written questions with reference ("gold") SQL, split simple / medium /
hard. `run_eval.py`:
- Runs every question through a chosen agent (`baseline` or `kg`)
- Executes both the agent's SQL and the gold SQL, normalizes both result sets
  (sorts rows, rounds numerics, trims to overlapping columns) and compares them
- Reports overall + per-difficulty accuracy, lists failed questions, saves a
  full CSV of every generated query and its pass/fail status

**Multi-trial mode** (`run_multi_trial()`): runs the full 15-question set
`n` times (default 3) per agent and reports mean accuracy, min–max range, and
a per-question **STABLE** (always pass/always fail) vs **FLAKY** (inconsistent
across trials) classification — added specifically because GPT-4o at
`temperature=0` is not perfectly deterministic run-to-run (OpenAI's own
documented behavior, due to server-side batching/parallelism), which showed
up as real accuracy swings between identical back-to-back runs.

```powershell
python -m tests.eval.run_eval baseline 3
python -m tests.eval.run_eval kg 3
```

**Final results:** baseline 53% (stable across trials); KG-powered 93% mean
(some variance concentrated in the hard tier, per the FLAKY/STABLE
breakdown in `tests/eval/kg_multitrial_results.csv`).

---

## Phase 6 — Dashboard (Streamlit)

### 6.1 Chart/insight selection (`src/agent/visualize.py`)

Given a question and the SQL result (as a DataFrame), asks GPT-4o to pick a
chart type (`bar` / `line` / `pie` / `table` / `metric` for single-value
results) and write a one-sentence insight, returned as strict JSON.

### 6.2 The app (`app.py`)

```powershell
pip install streamlit==1.35.0 plotly==5.22.0
streamlit run app.py
```
A single-page app: text box for the question → generated SQL shown as code →
auto-written insight → auto-selected Plotly chart (or `st.metric` for
single-value answers) → raw data in an expandable table.

**Operational note:** every run requires Postgres *and* the correct Neo4j
instance to be running simultaneously — the most common runtime error
(`neo4j.exceptions.ServiceUnavailable ... Connection refused ... 7687`) was
simply the Neo4j instance not yet being fully started (it can take 30–60+
seconds after clicking Start in Neo4j Desktop before Bolt is actually
listening), not a code or config problem.

---

## Troubleshooting log (real issues hit, and root causes)

| Symptom | Root cause | Fix |
|---|---|---|
| `psql`/Postgres commands fail after fresh install | New PowerShell window needed for updated PATH | Reopen terminal |
| `Neosemantics` not in Neo4j Desktop's plugin catalog | Plugin catalog doesn't list it for the installed Neo4j version | Manual JAR install (Phase 3.2) |
| Neo4j startup crash: `ComponentInjectionException ... apoc.Pools` | neosemantics JAR version mismatch vs. Neo4j core version | Pin a second Neo4j instance to 5.26.0 |
| `MATCH (c:Class)` returns nothing after ontology import | n10s labels imported classes `n4sch__Class`, not `Class` | Query the correct label |
| `CALL dbms.procedures()` errors with "no such procedure" | Deprecated Cypher syntax | Use `SHOW PROCEDURES` |
| `openai.OpenAI(...)` raises `TypeError: unexpected keyword argument 'proxies'` | Pinned `openai==1.30.1` incompatible with installed `httpx` | `pip install --upgrade openai` |
| `insufficient_quota` / `RateLimitError` despite valid billing | Stale system-level `OPENAI_API_KEY` env var shadowing `.env` | `load_dotenv(override=True)` |
| Postman `400 Bad Request: could not parse JSON body` | Raw-body mode wasn't set correctly | Body tab → raw → JSON |
| Multi-trial eval scores fluctuate run-to-run on hard questions | GPT-4o isn't perfectly deterministic at temperature=0 (documented OpenAI behavior) | Multi-trial averaging + STABLE/FLAKY classification |
| Streamlit `ServiceUnavailable` connecting to Neo4j | Neo4j instance still starting (30–60s) | Wait for `AVAILABLE` state before connecting |

---

## Reproducing this project from zero

1. Phase 0 (tools + project skeleton) → 30–60 min
2. Phase 1 (data + lakehouse) → 30–45 min
3. Phase 2 (ontology in Protégé) → 1–2 hours (manual UI work)
4. Phase 3 (knowledge graph) → 45–90 min (plus troubleshooting time if your
   Neo4j Desktop version also lacks the neosemantics plugin in its catalog)
5. Phase 4–5 (agents + evaluation) → 1–2 hours
6. Phase 6 (dashboard) → 20–30 min

Total: roughly a full day of focused work for someone following this document
without hitting the same troubleshooting detours.
