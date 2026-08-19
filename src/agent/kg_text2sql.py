"""
GraphRAG-powered Text-to-SQL agent: uses knowledge graph context
(business definitions, taxonomy, relationships, rules) in addition
to raw schema, to generate more accurate SQL.
"""

import os
from openai import OpenAI
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from src.kg.graph_retrieval import build_graph_context
from src.agent.baseline_text2sql import get_raw_schema, pg_engine

load_dotenv(override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_sql_with_kg(question, schema_text, graph_context):
    prompt = f"""You are a SQL expert with deep knowledge of this company's business domain. Given the following PostgreSQL database schema AND business knowledge graph context, write a single valid SQL query to answer the user's question.

Database Schema:
{schema_text}

Business Knowledge Graph Context:
{graph_context}

Rules:
- Use the business glossary and rules above to correctly interpret ambiguous business terms (e.g., "active customer", "profit margin", "revenue").
- Use the entity relationships to determine correct join paths.
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
    graph_context = build_graph_context(question)
    sql = generate_sql_with_kg(question, schema_text, graph_context)
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
    # Test on one of the "hard" questions the baseline got WRONG
    ask("How many active enterprise customers do we have?")