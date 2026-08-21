# Enterprise Text-to-SQL Agent — Knowledge Graph, Ontology & GraphRAG

An enterprise-grade Text-to-SQL agent that answers natural-language business
questions against a Postgres data warehouse. Two agents are built side by side —
a plain schema-only baseline and a GraphRAG-powered agent that retrieves context
from a Neo4j knowledge graph built on a formal OWL/SKOS ontology — so the value of
the semantic layer can be measured directly rather than assumed.

**Headline result:** the knowledge-graph-powered agent scored **~93% accuracy**
across three evaluation trials, versus **~53%** for the schema-only baseline, on a
15-question benchmark spanning simple, medium, and business-logic-dependent
questions. The gap is almost entirely in the "hard" tier — questions that depend on
business definitions a raw schema can't express (e.g., what counts as an "active"
customer, or which region a "revenue by region" question actually means).

---

## What's in this project

- **A synthetic enterprise lakehouse** (Postgres): bronze → silver → gold layers,
  ~50,000 orders / ~150,000 line items, built with intentional real-world messiness
  (duplicate records, mixed date formats, missing values) so the cleaning pipeline
  does real work.
- **A formal ontology** (OWL + SKOS, built in Protégé): business entity classes,
  a product/customer taxonomy, object properties (relationships), data properties,
  and logical restrictions (e.g., the formal definition of "EnterpriseCustomer").
- **A knowledge graph** (Neo4j + neosemantics): the ontology imported as a semantic
  layer, plus the actual gold-layer business data loaded as a connected graph —
  customers, orders, products, suppliers, stores, all linked.
- **Two Text-to-SQL agents** (GPT-4o): a baseline agent using only the raw
  schema, and a GraphRAG agent that retrieves business definitions, taxonomy, and
  correct join paths from the knowledge graph before generating SQL.
- **A rigorous evaluation harness**: a 15-question benchmark across simple/medium/hard
  difficulty, run across multiple trials to account for LLM non-determinism, with
  per-question pass-rate tracking to distinguish genuine capability gaps from noise.
- **A live dashboard** (Streamlit): ask a question in plain English, see the
  generated SQL, an auto-selected chart, and an auto-written insight.

## Architecture

See [`enterprise-architecture.png`](enterprise-architecture.png) for the full
visual, and [`FULL_WALKTHROUGH.md`](FULL_WALKTHROUGH.md) for a complete
step-by-step build log of every phase, tool, and decision.

## Results

| | Overall | Simple | Medium | Hard |
|---|---|---|---|---|
| Baseline (schema-only) | 53% | 100% | 60% | ~43% |
| GraphRAG (knowledge-graph-powered) | 93% | 100% | 60%* | ~71-93%** |

\* Medium-tier accuracy is unchanged by design — those questions don't depend on
business definitions the KG resolves, which is itself a useful negative result:
the KG helps exactly where it should and doesn't help (or hurt) elsewhere.
\*\* Range reflects run-to-run LLM variance on the hardest questions; see
`tests/eval/*_multitrial_results.csv` for the full per-trial breakdown.

## Repository layout

```
├── config/                  # settings, non-secret config
├── data/
│   ├── raw/                 # generated synthetic CSVs (see dataset package below)
│   ├── bronze/ silver/ gold/
├── FULL_WALKTHROUGH.md      # every phase, step by step, from a blank machine
├── enterprise-architecture.png
├── ontology/owl/            # enterprise_ontology.owl (Protégé)
├── sql/ddl/                 # bronze.sql, silver.sql, gold.sql
├── src/
│   ├── generation/          # generate_data.py (Faker)
│   ├── ingestion/           # load_bronze.py, transform_silver.py, transform_gold.py
│   ├── kg/                  # import_ontology.py, load_graph_data.py, graph_retrieval.py
│   └── agent/               # baseline_text2sql.py, kg_text2sql.py, visualize.py
├── tests/eval/               # eval_questions.py, run_eval.py, *_results.csv
├── app.py                    # Streamlit dashboard
├── requirements.txt
└── .env.template
```

## Quick start

**Prerequisites:** Python 3.10+, PostgreSQL, Neo4j Desktop (with `neosemantics`
and `APOC` plugins installed), an OpenAI API key.

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.template .env         # fill in your Postgres/Neo4j/OpenAI credentials

# 1. Generate data and build the lakehouse
python src\generation\generate_data.py
# run sql/ddl/bronze.sql, silver.sql, gold.sql against your Postgres DB, then:
python -m src.ingestion.load_bronze
python -m src.ingestion.transform_silver
python -m src.ingestion.transform_gold

# 2. Load the ontology and graph data into Neo4j
python -m src.kg.import_ontology
python -m src.kg.load_graph_data

# 3. Run the evaluation (compares baseline vs. KG-powered agent)
python -m tests.eval.run_eval baseline 3
python -m tests.eval.run_eval kg 3

# 4. Launch the dashboard
streamlit run app.py
```

For the fully detailed, click-by-click version of every one of these steps
(including Protégé screenshots-equivalent instructions, Neo4j plugin
troubleshooting, and every error encountered and fixed along the way), see
[`FULL_WALKTHROUGH.md`](FULL_WALKTHROUGH.md).

## Dataset

The generated dataset (CSVs + DDL) is packaged separately for easy reuse without
cloning the full repo: **`enterprise-lakehouse-dataset.zip`**. It's fully
reproducible from `src/generation/generate_data.py` (seeded, `Faker.seed(42)`).

## Known limitations

- LLM output isn't perfectly deterministic even at `temperature=0`; the eval
  harness accounts for this with multi-trial averaging, but single-run accuracy
  numbers can vary by a few percentage points.
- The GraphRAG agent still fails on some join-path questions that require chaining
  through the `silver` layer (a real schema gap, not a language model limitation) —
  see the "Known limitations" section of `FULL_WALKTHROUGH.md` for the specific
  failure case and root cause.
- The evaluation set is 15 questions — enough to show a clear signal, but a larger
  benchmark would give tighter confidence intervals.

## License / attribution

Synthetic data only — no real customer or business data is used anywhere in this
project.
