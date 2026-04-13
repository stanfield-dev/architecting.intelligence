import os
from urllib.parse import quote_plus

import psycopg
from psycopg.rows import dict_row

def dsn() -> str:
    host = os.environ["LLM_DB_HOST"]
    port = os.environ.get("LLM_DB_PORT", "5432")
    name = os.environ["LLM_DB_NAME"]
    user = os.environ["LLM_DB_USER"]
    pw = quote_plus(os.environ["LLM_DB_PASS"])
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}"

def write_llm_timing(
  llm_response_id,
  model,
  request_path,
  tool_used,
  total_ms,
  llm_ms,
  tool_ms,
  tool_followup_ms,
  summary_ms
):
    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """ 
                insert into llm_request_timing (llm_response_id, model, 
                  request_path, tool_used, total_ms, llm_ms, tool_ms,
                  tool_followup_ms, summary_ms)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (llm_response_id, model, request_path, tool_used,
                  total_ms, llm_ms, tool_ms, tool_followup_ms, summary_ms),
            )

def get_llm_metrics():
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  id,
                  request_path,
                  tool_used,
                  total_ms,
                  llm_ms,
                  tool_ms,
                  tool_followup_ms,
                  summary_ms
                from llm_request_timing
                order by id desc
                limit 1
                """
            )
            return cur.fetchone()