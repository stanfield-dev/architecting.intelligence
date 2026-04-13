import os
from urllib.parse import quote_plus

import psycopg
from psycopg.types.json import Json
from psycopg.rows import dict_row

def dsn() -> str:
    host = os.environ["LLM_DB_HOST"]
    port = os.environ.get("LLM_DB_PORT", "5432")
    name = os.environ["LLM_DB_NAME"]
    user = os.environ["LLM_DB_USER"]
    pw = quote_plus(os.environ["LLM_DB_PASS"])
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}"

def write_tool_response(response_id, model, tool_name, tool_result):
    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into tool_results (response_id, model, tool_name, tool_result)
                values (%s, %s, %s, %s)
                """,
                (response_id, model, tool_name, Json(tool_result)),
            )

def get_tool_response():
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  response_id,
                  model,
                  tool_name,
                  tool_result,
                  created_at
                from tool_results
                order by created_at desc
                limit 1
                """
            )
            return cur.fetchone()


