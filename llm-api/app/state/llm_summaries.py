import json
import os
from urllib.parse import quote_plus

from openai import OpenAI

import psycopg
from psycopg.types.json import Json
from psycopg.rows import dict_row

import app.state.context_cache as context_cache

def dsn() -> str:
    host = os.environ["LLM_DB_HOST"]
    port = os.environ.get("LLM_DB_PORT", "5432")
    name = os.environ["LLM_DB_NAME"]
    user = os.environ["LLM_DB_USER"]
    pw = quote_plus(os.environ["LLM_DB_PASS"])
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}"

def extract_text(response_blob):
    for item in response_blob.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    return c.get("text", "")
    return "" 

def create_summary(turns):

    client = OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )

    model = "qwen2.5:14b"

    summary_prompt = """
        Write exactly 2 short sentences summarizing the recent conversation.

        Include only:
        - any training activity mentioned
        - any health or recovery notes mentioned

        Rules:
        - plain text only
        - no markdown
        - no questions
        - no filler
        - do not leave the answer blank
        - if nothing meaningful is present, say: No meaningful training context in recent conversation.
    """

    messages = []

    last_summary = get_summary()
    summary_context_id = get_summary_context_id()

    if last_summary:
        summary_blob = last_summary["summary"]
        messages.append({
            "role": "system",
            "content": f"Previous summary checkpoint: {summary_blob}"
        })
    else:
        messages.append({
            "role": "system",
            "content": "Previous summary checkpoint: none"
        })

    if summary_context_id is None:
        history = context_cache.retrieve_context(turns)
    else:
        history = context_cache.retrieve_context_since_id(summary_context_id)

    history = history[-turns:]

    for row in history:
        messages.append({
            "role": "user",
            "content": row["user_query"]
        })

        #assistant_text = extract_text(row["response"])
        #if assistant_text:
        #    messages.append({
        #        "role": "assistant",
        #        "content": assistant_text
        #    })

    #response = client.responses.create(
    #    model=model,
    #    instructions="Reply with exactly this text: hello summary",
    #    input=[{"role": "user", "content": "say hello summary"}]
    #)

    response = client.responses.create(
        model=model,
        instructions=summary_prompt,
        input=messages
    )

    response_blob = response.model_dump()
    print(f"SUMMARY RAW RESPONSE: {response_blob!r}", flush=True)

    print(f"SUMMARY status: {response_blob.get('status')!r}", flush=True)
    print(f"SUMMARY incomplete_details: {response_blob.get('incomplete_details')!r}", flush=True)
    print(f"SUMMARY output: {response_blob.get('output')!r}", flush=True)
    print(f"SUMMARY output_text field: {response_blob.get('output_text')!r}", flush=True)

    summary_text = extract_text(response_blob)
    print(f"SUMMARY extracted: {summary_text!r}", flush=True)

    if not summary_text or not summary_text.strip():
        summary_text = "SUMMARY_TRIGGERED_BUT_MODEL_RETURNED_NO_TEXT"

    return summary_text.strip()

def write_summary(llm_response_id, model, summary, through_context_id):
    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into llm_summaries (llm_response_id, model, summary, through_context_id)
                values (%s, %s, %s, %s)
                """,
                (llm_response_id, model, summary, through_context_id),
            )

def get_summary():
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  id,
                  llm_response_id,
                  model,
                  summary,
                  through_context_id,
                  created_at
                from llm_summaries
                order by id desc
                limit 1
                """
            )
            return cur.fetchone()

def get_summary_context_id() -> int:
    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select 
                  through_context_id
                from llm_summaries
                order by created_at desc
                limit 1
                """
            )
            row = cur.fetchone()
            return row[0] if row else None
