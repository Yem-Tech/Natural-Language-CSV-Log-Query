"""Streamlit interface for the local CSV query engine."""
import csv
import os
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from openai import AuthenticationError, OpenAIError, RateLimitError

from log_query import plan_query, query_file, validate_plan


st.set_page_config(page_title="Natural Language Log Query", layout="wide")
st.title("Natural Language CSV Log Query")
st.caption("Ask a question. AI interprets it; Python searches the CSV locally.")

with st.sidebar:
    st.header("Configuration")
    supplied_key = st.text_input("OpenAI API key", type="password",
                                 help="Used for this session only; never included in result screenshots.")
    api_key = supplied_key or os.getenv("OPENAI_API_KEY")
    timezone = st.text_input("Log timezone", value="UTC",
                             help="For example America/Halifax. Offset-free timestamps are treated as local.")
    model = st.text_input("Model", value=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    limit = st.number_input("Maximum displayed rows", min_value=1, max_value=1000, value=100)

uploaded = st.file_uploader("Upload a CSV log file", type="csv")
use_sample = st.checkbox("Use the included sample logs", disabled=uploaded is not None)
if uploaded is not None:
    st.info(f"Selected: {uploaded.name} ({uploaded.size:,} bytes)")
elif use_sample:
    st.info("Using the six-row synthetic sample_logs.csv")
else:
    st.info("Upload a CSV or select the sample to begin.")

st.write("Examples: **Show me users who accessed the courses section** · "
         "**Who logged in after working hours yesterday?** · "
         "**How many failed login attempts are in the logs?** · "
         "**Count log events by user_name**")
with st.form("query_form"):
    question = st.text_input("Your question")
    submitted = st.form_submit_button("Run query", type="primary")

if submitted:
    if not question.strip():
        st.warning("Enter a question first.")
    elif uploaded is None and not use_sample:
        st.warning("Choose a CSV file or the included sample.")
    elif not api_key:
        st.warning("Enter your OpenAI API key in the sidebar.")
    else:
        temporary_path = None
        try:
            if uploaded is None:
                path = Path(__file__).with_name("sample_logs.csv")
            else:
                uploaded.seek(0)
                with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                    shutil.copyfileobj(uploaded, tmp)
                    temporary_path = Path(tmp.name)
                path = temporary_path
            with path.open(newline="", encoding="utf-8-sig") as stream:
                columns = csv.DictReader(stream).fieldnames or []
            if not columns:
                raise ValueError("The CSV needs a header row.")
            with st.spinner("Interpreting question and searching logs..."):
                plan = validate_plan(plan_query(question, columns, model, api_key), columns)
                result = query_file(path, plan, timezone, int(limit))
            st.metric("Matching events", result["matching_events"])
            if plan["intent"] == "search":
                if result["rows"]:
                    st.dataframe(pd.DataFrame(result["rows"]), hide_index=True, use_container_width=True)
                    if result["shown"] < result["matching_events"]:
                        st.info(f"Showing the first {result['shown']} matching rows.")
                else:
                    st.info("No matching events found.")
            elif plan["intent"] == "group":
                groups = [{plan["group_by"]: key, "events": count}
                          for key, count in sorted(result["groups"].items(), key=lambda x: (-x[1], x[0]))]
                st.dataframe(pd.DataFrame(groups), hide_index=True, use_container_width=True)
            with st.expander("How the question was interpreted"):
                st.json(plan)
                st.caption(f"Dates use {result['timezone']}; today is {result['date']} in that zone.")
        except AuthenticationError:
            st.error("The API key was rejected. Check the key in the sidebar.")
        except RateLimitError:
            st.error("API quota or rate limit reached. Check your API billing and limits.")
        except OpenAIError as exc:
            st.error(f"OpenAI API request failed: {exc}")
        except (OSError, ValueError, KeyError, UnicodeError) as exc:
            st.error(f"Could not run query: {exc}")
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
