"""
Baseline Text-to-SQL agent: schema-only prompting, NO knowledge graph,
NO ontology, NO semantic layer. This is the control group we'll compare
against the GraphRAG-powered agent in Phase 5.
"""

import os
from openai import OpenAI
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(override=True)

PG_HOST = os.getenv("POSTGRES_HOST")
PG_PORT = os.getenv("POSTGRES_PORT")
PG_DB = os.getenv("POSTGRES_DB")
PG_USER = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")

pg_engine = create_engine(
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_raw_schema():
    """
    Dumps the raw gold schema (table + column names/types only) —
    exactly what a naive Text-to-SQL approach would give the LLM,
    with NO business context, NO definitions, NO relationships explained.
    """
    query = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'gold'
        ORDER BY table_name, ordinal_position;
    """
    with pg_engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()

    schema_by_table = {}
    for table_name, column_name, data_type in rows:
        schema_by_table.setdefault(table_name, []).append(f"{column_name} ({data_type})")

    schema_text = ""
    for table, columns in schema_by_table.items():
        schema_text += f"\nTable: gold.{table}\nColumns: {', '.join(columns)}\n"

    return schema_text


def generate_sql(question, schema_text):
    prompt = f"""You are a SQL expert. Given the following PostgreSQL database schema, write a single valid SQL query to answer the user's question.

Schema:
{schema_text}

Rules:
- Return ONLY the SQL query, no explanation, no markdown code fences.
- Use fully qualified table names (schema.table).
- When using ORDER BY with LIMIT, add a deterministic secondary sort key (e.g. a name or id column) so results are reproducible even when the primary sort value has ties.
- For questions asking "which X is the most/highest/least/lowest Y" with a singular noun, return only the single top-ranked row (LIMIT 1) unless the question explicitly asks for multiple (e.g. "top N", a plural noun like "which suppliers").

Question: {question}

SQL:"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    sql = response.choices[0].message.content.strip()
    # Strip markdown fences if the model adds them anyway
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql


def execute_sql(sql):
    try:
        with pg_engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
            columns = list(result.keys())
            return {"success": True, "columns": columns, "rows": rows, "error": None}
    except Exception as e:
        return {"success": False, "columns": None, "rows": None, "error": str(e)}


def ask(question):
    schema_text = get_raw_schema()
    sql = generate_sql(question, schema_text)
    print(f"\nQuestion: {question}")
    print(f"Generated SQL:\n{sql}\n")

    result = execute_sql(sql)
    if result["success"]:
        print(f"Result ({len(result['rows'])} rows):")
        print(result["columns"])
        for row in result["rows"][:10]:
            print(row)
    else:
        print(f"SQL ERROR: {result['error']}")

    return sql, result


if __name__ == "__main__":
    # Quick manual test
    ask("What is the total revenue by product category?")