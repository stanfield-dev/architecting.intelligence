### ONLY RUN THIS FROM AWS LLM HOST ###
from collections import OrderedDict
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
import matplotlib.pyplot as plot
import numpy as np
import psycopg
from psycopg.rows import dict_row


FILENAME_LATENCY = "/home/ubuntu/harness-output/plots/qwen2.5_14b-LATENCY-2_turns.png"
FILENAME_TOKENS = "/home/ubuntu/harness-output/plots/qwen2.5_14b-TOKENS-2_turns.png"

load_dotenv("/etc/llm-api.env")

def dsn() -> str:
    host = os.environ["LLM_DB_HOST"]
    port = os.environ.get("LLM_DB_PORT", "5432")
    name = os.environ["LLM_DB_NAME"]
    user = os.environ["LLM_DB_USER"]
    pw = quote_plus(os.environ["LLM_DB_PASS"])
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}"

def harness_plot():
    ### LATENCY METRICS
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select id, total_ms, llm_ms, tool_ms, tool_followup_ms, summary_ms
                from llm_request_timing
                order by id
            """)
            rows = cur.fetchall()

    turns = list(range(1, len(rows) + 1))

    total_ms = [r["total_ms"] or 0 for r in rows]
    llm_ms = [r["llm_ms"] or 0 for r in rows]
    tool_ms = [r["tool_ms"] or 0 for r in rows]
    tool_followup_ms = [r["tool_followup_ms"] or 0 for r in rows]
    summary_ms = [r["summary_ms"] or 0 for r in rows]

    x = np.arange(len(turns))  # base positions
    width = 0.15              # bar width

    plot.figure(figsize=(12, 6))

    plot.bar(x - 2*width, total_ms, width, label="total")
    plot.bar(x - width,   llm_ms,   width, label="llm")
    plot.bar(x,           tool_ms,  width, label="tool")
    plot.bar(x + width,   tool_followup_ms, width, label="tool followup")
    plot.bar(x + 2*width, summary_ms, width, label="summary creation")

    plot.xticks(x, turns)

    plot.xlabel("Turn")
    plot.ylabel("Latency (ms)")
    plot.title("LLM Latency per Turn")
    plot.legend()

    plot.tight_layout()
    plot.savefig(FILENAME_LATENCY, dpi=300, transparent=True)

    ### TOKEN USAGE
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select id, response_id, metric_type, token_count, created_at
                from profile_data
                order by created_at, id
            """)
            rows = cur.fetchall()

    data = OrderedDict()

    for r in rows:
        rid = r["response_id"]

        if rid not in data:
            data[rid] = {}

        data[rid][r["metric_type"]] = r["token_count"]

    metric_types = [
        "PROMPT_TOKENS",
        "INPUT_CONTEXT_TOKENS",
        "RESPONSE_OUTPUT_TOKENS",
        "TOOL_CALL_EMIT_TOKENS",
        "TOOL_RESULT_TOKENS",
        "FOLLOWUP_OUTPUT_TOKENS",
        "SUMMARY_UPDATE_TOKENS",
    ]

    turns = []
    series = {m: [] for m in metric_types}

    for i, (rid, metrics) in enumerate(data.items(), start=1):
        turns.append(i)

        for m in metric_types:
            series[m].append(metrics.get(m, 0))  # <-- handles missing

    bottom = [0] * len(turns)

    plot.figure(figsize=(12, 6))

    for m in metric_types:
        plot.bar(turns, series[m], bottom=bottom, label=m)
        bottom = [b + v for b, v in zip(bottom, series[m])]

    plot.xlabel("Turn")
    plot.ylabel("Tokens")
    plot.title("Token Usage per Turn")
    plot.legend()

    plot.tight_layout()
    plot.savefig(FILENAME_TOKENS, dpi=300, transparent=True)

if __name__ == "__main__":
    harness_plot()
