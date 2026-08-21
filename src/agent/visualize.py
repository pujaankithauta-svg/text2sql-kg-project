"""
Given a question and a SQL result (as a DataFrame), asks GPT-4o to
choose an appropriate chart type and write a short business insight.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def choose_visualization(question, df):
    """
    Returns a dict: {"chart_type": "bar"|"line"|"pie"|"table",
                      "x_col": str, "y_col": str, "insight": str}
    """
    # Don't bother calling the LLM for single-value results
    if df.shape[0] == 1 and df.shape[1] == 1:
        value = df.iloc[0, 0]
        return {
            "chart_type": "metric",
            "x_col": None,
            "y_col": df.columns[0],
            "insight": f"The answer to '{question}' is {value}.",
        }

    sample = df.head(10).to_string(index=False)
    columns = list(df.columns)

    prompt = f"""Given this question and query result, choose the best chart type and write a one-sentence business insight.

Question: {question}
Columns: {columns}
Sample data:
{sample}

Respond ONLY with valid JSON in this exact format, no markdown fences:
{{"chart_type": "bar" or "line" or "pie" or "table", "x_col": "<column name for x-axis/categories>", "y_col": "<column name for y-axis/values>", "insight": "<one sentence insight about what this data shows>"}}

Rules:
- Use "bar" for comparing categories (e.g. revenue by category, top N items)
- Use "line" only if there's a clear date/time column
- Use "pie" only for percentage/share-of-whole breakdowns with few (<=6) categories
- Use "table" if the data doesn't fit a simple chart (too many columns, no clear x/y)
- x_col and y_col must be exact column names from the Columns list above
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Safe fallback if the model's JSON is malformed
        return {
            "chart_type": "table",
            "x_col": columns[0],
            "y_col": columns[-1],
            "insight": f"Results for: {question}",
        }
