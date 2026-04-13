###
###
### ONLY RUN FROM AWS LLM HOST!!!!
###
###

# a basic harness to query the LLM with a fixed set of questions purposefully crafted to 
# test various capabilities:
#
# Memory / summarization
# 	•	q4
# 	•	q8
# 	•	q11
# 	•	q16
# 
# Tool selection / retrieval
# 	•	q3
# 	•	q5
# 	•	q9
# 	•	q12
# 	•	q18
# 
# Cross-domain synthesis
# 	•	q2
# 	•	q6
# 	•	q10
# 	•	q15
# 
# Coaching / planning
# 	•	q13
# 	•	q14
# 
# User-supplied contextual state
# 	•	q7 feeding q14
# 

import asyncio
from datetime import datetime

from dotenv import load_dotenv
import httpx

from app.state.llm_summaries import get_summary
from app.utility.timing import get_llm_metrics

load_dotenv("/etc/llm-api.env")

# AWS LLM_API
#LLM_API_BASE = "http://llm.stanfield-lab.aws:8000"
LLM_API_BASE = "http://127.0.0.1:8000"

# how many turns before a summary should be created (match this to llm_api/routes/chat.py)
TURNS = 2

# model being tested
MODEL = "qwen2.5_14b"

# output file for the test
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
OUTPUT_FILE = f"/home/ubuntu/harness-output/{MODEL}-{TURNS}_turns-{TIMESTAMP}.txt"

async def query_llm(user_query: str) -> str:

    try:
        timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                f"{LLM_API_BASE}/query-llm",
                params={"user_query": user_query},
            )
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to reach LLM service at {LLM_API_BASE}: {e}") from e

    if r.status_code != 200:
        raise RuntimeError(f"LLM query failed: {r.status_code} {r.text}")

    return r.text

async def run_harness():

    questions = [
        "hi my name is eric, im 53y old, and I live in colorado",

        ("ive just started the 3rd phase of a three month training arc preparing for a local mountain run scheduled "
        "for may 2.  review my journal entries for the months of february and march, and analyze any trends (positive "
        "or negative) in my resting HR and HRV."),

        "how long was my run on tuesday march 31st?",

        "what is my name and age?",

        "how long was my last run?",

        ("look at my run on saturday april 4th, and tell me what impact it may have had on my resting HR and HRV values "
        "as recorded on the following day"),

        "after my run on saturday the 4th, my left knee was pretty sore.  just letting you know.",

        "remind me, what date is my mountain run scheduled for?",

        "give me the max HR values for each mile segment of my run on wednesday April 1st",

        "review my journal entries for the past week.  do you notice any issues?",

        "how old am i?",

        "when was my last bike ride?",

        ("review my activities for the past month, and give me a plan for the following week that provides me with daily "
        "run, ride, or rest activities with associated distance or activity time goals that will help me improve my "
        "fitness"),

        ("look at the total elevation gain for each of my last three runs and advise as to any concerns you may have as to "
        "what impact these type of runs may have given my physical condition"),

        "do you see any notable trends across my activities for the last month?",

        "where do i live?",

        "ignoring all conversation to date, tell me how long (both time and distance) my last run was",

        "how many runs have I completed in the last two weeks?",
    ]

    header = (
        f"====================================================================\n\n"
        f"MODEL: {MODEL}\n"
        f"TURNS: {TURNS}\n\n"
        f"TEST DATE: {TIMESTAMP}\n\n"
        f"====================================================================\n\n"
    )

    with open(OUTPUT_FILE, "a") as f:
        f.write(header)
    
        last_summary_id = 0
        last_metrics_id = 0

        for i, question in enumerate(questions, start=1):
            response = await query_llm(question)
            response = response.replace("\\n", "\n").replace("\\t", "\t")

            # check to see if a summary has been created
            summary_text = None
            context_summary = get_summary()

            if context_summary and context_summary["id"] > last_summary_id:
                summary_text = context_summary["summary"]
                last_summary_id = context_summary["id"]

            # grab latency metrics
            request_path = None
            tool_used = False
            total_ms = 0
            llm_ms = 0
            tool_ms = 0
            tool_followup_ms = 0
            summary_ms = 0

            llm_latency_metrics = get_llm_metrics()

            if llm_latency_metrics and llm_latency_metrics["id"] > last_metrics_id:
                request_path = llm_latency_metrics["request_path"]
                tool_used = llm_latency_metrics["tool_used"]
                total_ms = llm_latency_metrics["total_ms"]
                llm_ms = llm_latency_metrics["llm_ms"]
                tool_ms = llm_latency_metrics["tool_ms"]
                tool_followup_ms = llm_latency_metrics["tool_followup_ms"]
                summary_ms = llm_latency_metrics["summary_ms"]

                last_metrics_id = llm_latency_metrics["id"]

            # write to the output file
            output = (
                f"TEST {i}\n\n"
                f"Q: {question}\n\n"
                f"A: {response}\n\n"
                f"SUMMARY_CREATED: {'YES' if summary_text else 'NO'}\n"
                f"SUMMARY: {summary_text or ''}\n\n"
                f"LLM LATENCY:\n"
                f"  request path:          {request_path}\n"
                f"  tool used:             {tool_used}\n"
                f"  total (ms):            {total_ms}\n"
                f"  llm (ms):              {llm_ms}\n"
                f"  tool (ms):             {tool_ms}\n"
                f"  tool followup (ms):    {tool_followup_ms}\n"
                f"  summary creation (ms): {summary_ms}\n\n"
                f"====================================================================\n\n"
            )

            f.write(output)

            print("#", end="", flush=True)
        
    print()

if __name__ == "__main__":
    asyncio.run(run_harness())


