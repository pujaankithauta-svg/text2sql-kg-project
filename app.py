"""
Streamlit dashboard: ask a business question in plain English,
see the generated SQL, the result as an auto-chosen chart,
and an auto-generated insight — powered by the KG Text-to-SQL agent.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from src.agent.kg_text2sql import generate_sql_with_kg, execute_sql
from src.agent.baseline_text2sql import get_raw_schema, pg_engine
from src.kg.graph_retrieval import build_graph_context
from src.agent.visualize import choose_visualization

st.set_page_config(page_title="Enterprise KG Text-to-SQL", layout="wide")

st.title("Enterprise Text-to-SQL Agent")
st.caption("Powered by GraphRAG + Ontology + Neo4j Knowledge Graph")

if "graph_context" not in st.session_state:
    with st.spinner("Loading knowledge graph context..."):
        st.session_state.graph_context = build_graph_context()
        st.session_state.schema_text = get_raw_schema()

question = st.text_input(
    "Ask a business question:",
    placeholder="e.g. How many active enterprise customers do we have?",
)

if st.button("Run") and question:
    with st.spinner("Generating SQL..."):
        sql = generate_sql_with_kg(
            question, st.session_state.schema_text, st.session_state.graph_context
        )

    st.subheader("Generated SQL")
    st.code(sql, language="sql")

    result = execute_sql(sql)

    if not result["success"]:
        st.error(f"SQL Error: {result['error']}")
    else:
        df = pd.DataFrame(result["rows"], columns=result["columns"])

        if df.empty:
            st.warning("Query ran successfully but returned no rows.")
        else:
            with st.spinner("Generating visualization..."):
                viz = choose_visualization(question, df)

            st.subheader("Insight")
            st.info(viz["insight"])

            st.subheader("Result")

            chart_type = viz.get("chart_type")
            x_col = viz.get("x_col")
            y_col = viz.get("y_col")

            try:
                if chart_type == "metric":
                    st.metric(label=y_col, value=str(df.iloc[0, 0]))
                elif chart_type == "bar" and x_col in df.columns and y_col in df.columns:
                    fig = px.bar(df, x=x_col, y=y_col)
                    st.plotly_chart(fig, use_container_width=True)
                elif chart_type == "line" and x_col in df.columns and y_col in df.columns:
                    fig = px.line(df, x=x_col, y=y_col)
                    st.plotly_chart(fig, use_container_width=True)
                elif chart_type == "pie" and x_col in df.columns and y_col in df.columns:
                    fig = px.pie(df, names=x_col, values=y_col)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.dataframe(df, use_container_width=True)
            except Exception:
                # If chart rendering fails for any reason, fall back to a table
                st.dataframe(df, use_container_width=True)

            with st.expander("Raw data"):
                st.dataframe(df, use_container_width=True)