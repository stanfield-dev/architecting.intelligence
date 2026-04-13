import os
from urllib.parse import quote_plus

import tiktoken
import psycopg
from psycopg.rows import dict_row

def dsn() -> str:
    host = os.environ["LLM_DB_HOST"]
    port = os.environ.get("LLM_DB_PORT", "5432")
    name = os.environ["LLM_DB_NAME"]
    user = os.environ["LLM_DB_USER"]
    pw = quote_plus(os.environ["LLM_DB_PASS"])
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}"

def profile_tokens(input_text, response_id, model, metric_type) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    token_count = len(enc.encode(input_text))

    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into profile_data (response_id, model, metric_type, token_count)
                values (%s, %s, %s, %s)
                on conflict (response_id, metric_type)
                do update set token_count = excluded.token_count;
                """,
                (response_id, model, metric_type, token_count),
            )

    return token_count

def get_profile_data(limit: int = 100):
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  response_id,
                  model,
                  metric_type,
                  token_count,
                  created_at
                from profile_data
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            return cur.fetchall()

