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

def update_context(llm_response_id, user_query, model, response) -> int:
    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into context_cache (llm_response_id, user_query, model, response)
                values (%s, %s, %s, %s)
                returning id
                """,
                (llm_response_id, user_query, model, Json(response)),
            )
            return cur.fetchone()[0]


def retrieve_context(turns: int):
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            #grab last 10 entries, then re-sort in conversation flow order
            cur.execute(
                """
                select
                  llm_response_id,
                  user_query,
                  model,
                  response
                from (
                    select
                      llm_response_id,
                      user_query,
                      model,
                      response,
                      created_at
                    from context_cache
                    order by created_at desc
                    limit %s
                ) sub
                order by created_at asc;
                """,
                (turns,)
            )
            return cur.fetchall()

def retrieve_context_since_id(context_id: int):
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  id,
                  llm_response_id,
                  user_query,
                  model,
                  response
                from context_cache
                where id > %s
                order by id asc
                """,
                (context_id,),
            )
            return cur.fetchall()
