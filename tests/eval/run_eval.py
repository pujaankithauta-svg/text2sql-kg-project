"""
Evaluation runner: executes every question in eval_questions.py through
a given Text-to-SQL agent, compares results against the gold SQL,
and reports accuracy.

Usage: python tests/eval/run_eval.py
"""

import sys
import os
from pathlib import Path

# Allow importing from src/
sys.path.append(str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import pandas as pd

from tests.eval.eval_questions import EVAL_QUESTIONS
#from src.agent.baseline_text2sql import generate_sql, get_raw_schema, pg_engine
from src.agent.baseline_text2sql import get_raw_schema, pg_engine
from src.agent.baseline_text2sql import generate_sql as generate_sql_baseline
from src.agent.kg_text2sql import generate_sql_with_kg
from src.kg.graph_retrieval import build_graph_context

load_dotenv(override=True)


def run_sql_safe(sql):
    """Run SQL, return a normalized DataFrame or None on error."""
    try:
        with pg_engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
        return df
    except Exception as e:
        return None


def normalize_df(df):
    """
    Normalize a result DataFrame so comparison isn't broken by
    column order, row order, or minor float precision.
    """
    if df is None or df.empty:
        return None
    df = df.copy()
    # Round any numeric columns to 2 decimals for fair comparison
    for col in df.select_dtypes(include=["float", "object"]).columns:
        try:
            df[col] = pd.to_numeric(df[col]).round(2)
        except (ValueError, TypeError):
            pass
    # Sort rows and reset index so row order doesn't matter
    df = df.sort_values(by=list(df.columns)).reset_index(drop=True)
    return df


def results_match(agent_df, gold_df):
    agent_norm = normalize_df(agent_df)
    gold_norm = normalize_df(gold_df)

    if agent_norm is None and gold_norm is None:
        return True
    if agent_norm is None or gold_norm is None:
        return False

    if agent_norm.shape[0] != gold_norm.shape[0]:
        return False

    # If agent returned extra columns beyond gold's column count,
    # only compare the last N columns (typically the actual metric values),
    # since agents sometimes add helpful identifier columns (e.g. product_id
    # alongside product_name) that don't change correctness.
    gold_col_count = gold_norm.shape[1]
    agent_col_count = agent_norm.shape[1]

    if agent_col_count > gold_col_count:
        agent_norm = agent_norm.iloc[:, -gold_col_count:]
    elif gold_col_count > agent_col_count:
        gold_norm = gold_norm.iloc[:, -agent_col_count:]

    try:
        agent_values = agent_norm.values.tolist()
        gold_values = gold_norm.values.tolist()
        return sorted(map(str, agent_values)) == sorted(map(str, gold_values))
    except Exception:
        return False


def run_evaluation(agent_name="baseline"):
    print(f"\n{'='*60}")
    print(f"Running evaluation for agent: {agent_name}")
    print(f"{'='*60}\n")

    schema_text = get_raw_schema()
    results = []

    for q in EVAL_QUESTIONS:
        print(f"[{q['id']}] ({q['difficulty']}) {q['question']}")

        if agent_name == "kg":
            graph_context = build_graph_context(q["question"])
            agent_sql = generate_sql_with_kg(q["question"], schema_text, graph_context)
        else:
            agent_sql = generate_sql_baseline(q["question"], schema_text)

        agent_df = run_sql_safe(agent_sql)
        gold_df = run_sql_safe(q["gold_sql"])

        sql_executed = agent_df is not None
        correct = results_match(agent_df, gold_df) if sql_executed else False

        status = "PASS" if correct else ("SQL_ERROR" if not sql_executed else "WRONG_RESULT")
        print(f"    -> {status}")

        results.append({
            "id": q["id"],
            "difficulty": q["difficulty"],
            "question": q["question"],
            "agent_sql": agent_sql,
            "sql_executed": sql_executed,
            "correct": correct,
            "status": status,
        })

    return results


def print_summary(results, agent_name="baseline"):
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    sql_errors = sum(1 for r in results if not r["sql_executed"])

    print(f"\n{'='*60}")
    print(f"SUMMARY: {agent_name}")
    print(f"{'='*60}")
    print(f"Overall accuracy: {correct}/{total} ({100*correct/total:.1f}%)")
    print(f"SQL execution errors: {sql_errors}/{total}")

    for difficulty in ["simple", "medium", "hard"]:
        subset = [r for r in results if r["difficulty"] == difficulty]
        sub_correct = sum(1 for r in subset if r["correct"])
        print(f"  {difficulty.capitalize()}: {sub_correct}/{len(subset)} ({100*sub_correct/len(subset):.1f}%)")

    print("\nFailed questions:")
    for r in results:
        if not r["correct"]:
            print(f"  [{r['id']}] {r['question']} -> {r['status']}")


if __name__ == "__main__":
    agent_to_run = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    if agent_to_run not in ("baseline", "kg"):
        sys.exit(
            f"Unknown agent '{agent_to_run}'. Must be exactly 'baseline' or 'kg' "
            f"(pass a second argument for a run label, e.g. 'kg v4')."
        )
    run_label = sys.argv[2] if len(sys.argv) > 2 else agent_to_run

    results = run_evaluation(agent_to_run)
    print_summary(results, run_label)

    df = pd.DataFrame(results)
    output_path = Path(__file__).resolve().parent / f"{run_label}_results.csv"
    df.to_csv(output_path, index=False)
    print(f"\nResults saved to {output_path}")