import json
from datetime import datetime
from zoneinfo import ZoneInfo
from time import perf_counter

from fastapi import APIRouter, Query
from openai import OpenAI

from app.tools.tool_definitions import tools
from app.tools.tool_dispatcher import request_tool

from app.state.llm_summaries import create_summary, get_summary_context_id, write_summary
from app.state.tool_results import write_tool_response
import app.state.context_cache as context_cache

from app.utility.profiler import profile_tokens
from app.utility.timing import write_llm_timing

# if set, disable actual LLM interaction and simulate responses
DEBUG = 0

# if set, insert tool responses into tool_results table
LOG_TOOL_RESULTS = 1

# if set, log token counts for various inputs/outputs 
PROFILER = 1

#mock responses when in DEBUG mode
class MockItem:
    def __init__(self, item_type, content=None, text=None, name=None, arguments=None, call_id=None):
        self.type = item_type
        self.content = content or []
        self.text = text
        self.name = name
        self.arguments = arguments
        self.call_id = call_id

    def model_dump(self):
        data = {
            "type": self.type,
        }

        if self.content:
            data["content"] = [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in self.content
            ]
        if self.text is not None:
            data["text"] = self.text
        if self.name is not None:
            data["name"] = self.name
        if self.arguments is not None:
            data["arguments"] = self.arguments
        if self.call_id is not None:
            data["call_id"] = self.call_id

        return data

class MockContent:
    def __init__(self, text):
        self.type = "output_text"
        self.text = text

    def model_dump(self):
        return {
            "type": self.type,
            "text": self.text,
        }


class MockUsage:
    def __init__(self, input_tokens=123, output_tokens=45, total_tokens=168):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens

    def model_dump(self):
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }

class MockResponse:
    def __init__(self, response_id, text, include_function_call=False):
        self.id = response_id
        self.output = []

        if include_function_call:
            self.output.append(
                MockItem(
                    item_type="function_call",
                    name="query_activities",
                    arguments="{}",
                    call_id="debug-call-1",
                )
            )

        self.output.append(
            MockItem(
                item_type="message",
                content=[MockContent(text)],
            )
        )

        self.output_text = text

        self.usage = MockUsage()
    

    def model_dump(self):
        return {
            "id": self.id,
            "output": [item.model_dump() for item in self.output],
            "output_text": self.output_text,
            "usage": self.usage.model_dump(),
        }

def extract_text(response_blob):
    for item in response_blob.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    return c.get("text", "")
    return "" 

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

chat_router = APIRouter()

prompt = """
You are an AI endurance training coach assisting an athlete inside the Training Ledger system.

Your role:
- Provide accurate, grounded analysis of training, recovery, workload, consistency, and recent performance.
- Give practical coaching guidance based only on the data available through the conversation and approved tools.
- Be clear, direct, and specific.
- Always respond in English.

Core rules:
- Never invent facts, dates, workouts, metrics, trends, or tool results.
- If data is missing, incomplete, or ambiguous, say so plainly.
- When a tool is used, you MUST base your answer ONLY on the tool output.
- Do not use prior knowledge, assumptions, or generic templates when answering tool-based questions.
- If the tool output does not directly answer the question, say so.
- For questions involving counts, totals, or comparisons, you must compute the answer directly from the tool output before responding.
- Do not answer questions about training history without using tools when appropriate.
- Do not claim to have checked training data unless you actually used the relevant tool or were given the data in the conversation.
- Do not infer that a workout happened unless it is explicitly present in the data.
- Do not diagnose injuries or medical conditions. When relevant, note uncertainty and stay within training/coaching scope.

Tool policy for query_activities:
- Use this tool for any question about recorded workouts, training volume, recent activity, recovery journal context, or comparisons across dates.
- Prefer the narrowest date range that fully answers the question.
- Prefer the narrowest activity_type that fits the request.
- Use activity_type="all" only when the question truly requires combining endurance, strength, and/or journal data.
- Use detail_level="summary" for recaps and totals.
- Use detail_level="metrics" for overall performance analysis, comparisons, and workout-level metrics.
- Use detail_level="detail" for split-level, segment-level, lap-level, and mile-by-mile inspection.
- Do not claim facts about the athlete's training history unless they come from this tool or from data already provided in the conversation.
- Journal contains daily resting HR, HRV, body weight and adhoc athlete notes.
- Endurance activity descriptions generally contain workout parameters/goals that guided the effort.
- If the user asks for segment, split, lap, or mile-by-mile data, use detail_level="detail".

Examples of tool usage for query_activities:

  User: How many miles did I run last week?
  Assistant: Use query_activities with activity_type="endurance", detail_level="summary", and the date range covering last week.

  User: How did my recovery look for the last three days?
  Assistant: Use query_activities with activity_type="journal", detail_level="summary", and the last three calendar dates.

  User: Compare my heart rate and pace from my last two runs.
  Assistant: Use query_activities with activity_type="endurance", detail_level="metrics", and a date range covering the last several days needed to include the last two runs.

  User: analyze my pace and heart rate per mile in my last run on DATE.
  Assistant: Use query_activities with activity_type="endurance", detail_level="detail", and a date range starting and ending on the DATE provided by the user.

Date and unit rules:
- Always use the date provided in the user query or system context. Never invent today's date.
- For running activities, convert speed to pace in minutes per mile when presenting it to the user.
- Convert kilometers to miles.
- Convert meters to feet.
- Prefer concise, human-readable units and rounded values unless precision is important.

Reasoning and analysis rules:
- Separate facts, interpretations, and recommendations.
- Base conclusions on evidence from the available data.
- Do not overgeneralize from a single workout or a single day of metrics.
- Trends are more important than isolated outliers.
- If evidence is weak, explicitly say that confidence is low.
- When the user asks about recent training, recovery, trends, load, readiness, or comparisons across time, use tools when needed before answering.

Coaching style:
- Be practical, not generic.
- Prioritize consistency, recovery, and sustainable progression over dramatic recommendations.
- Keep recommendations actionable.
- Avoid motivational filler, hedging, or unnecessary verbosity.

Response structure:
- Start with the direct answer.
- Then provide a brief evidence-based explanation.
- Then provide practical next steps only if useful.
- When appropriate, clearly label:
  - Facts
  - Interpretation
  - Recommendation
- Avoid repeating known context unless necessary.
"""

@chat_router.get("/query-llm")
async def query_llm(
    user_query: str = Query(...),
):

    # latency metrics captured along the way
    start_time = perf_counter()
    llm_start_time = None
    llm_end_time = None
    tool_start_time = None
    tool_end_time = None
    tool_followup_start_time = None
    tool_followup_end_time = None
    summary_start_time = None
    summary_end_time = None

    model = "qwen2.5:14b"
    TURNS = 2

    # fetch last TURNS turns of conversation
    history = context_cache.retrieve_context(TURNS)

    #today = datetime.now().strftime("%Y-%m-%d")
    today = datetime.now(ZoneInfo("America/Denver")).strftime("%Y-%m-%d")

    messages = []

    for row in history:
        uq = row["user_query"]

        messages.append({
            "role": "user",
            "content": uq
        })

        assistant_text = extract_text(row["response"])
        if assistant_text:
            messages.append({
                "role": "assistant",
                "content": assistant_text
            })

    # add the current query
    messages.append({
        "role": "user",
        "content": f"{user_query}"
    })

    if DEBUG:
        response = MockResponse(
            "debug-response-1",
            f"DEBUG MODE: mock response text, user asked: \"{user_query}\"",
            include_function_call=False
        )
    else:
        llm_start_time = perf_counter()

        response = client.responses.create(
            model=model,
            instructions=f"Today's date is {today}. {prompt}",
            tools=tools,
            input=messages
        )

        llm_end_time = perf_counter()

        if PROFILER:
            profile_tokens(prompt, response.id, model, "PROMPT_TOKENS")
            profile_tokens(json.dumps(messages), response.id, model, "INPUT_CONTEXT_TOKENS")

    for item in response.output:
        if item.type == "function_call":
            if DEBUG:
                followup = MockResponse(
                    "debug-followup-1",
                    "DEBUG MODE: mock TOOL response text",
                    include_function_call=False
                )
            else:
                tool_name = item.name
                tool_args = json.loads(item.arguments or "{}")

                tool_start_time = perf_counter()

                tool_result = await request_tool(tool_name, tool_args)

                tool_end_time = perf_counter()               

                if LOG_TOOL_RESULTS:
                    if tool_result is not None:
                        write_tool_response(response.id, model, tool_name, tool_result)

                tool_followup_input = [
                    *messages,
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": json.dumps(tool_result),
                    },
                ]

                tool_followup_start_time = perf_counter()

                followup = client.responses.create(
                    model=model,
                    instructions=prompt,
                    input=tool_followup_input,
                )

                tool_followup_end_time = perf_counter()

                if PROFILER:
                    tool_call_emit = {
                        "type": item.type,
                        "name": item.name,
                        "arguments": item.arguments,
                        "call_id": item.call_id,
                    }
                    profile_tokens(
                        json.dumps(tool_call_emit),
                        response.id,
                        model,
                        "TOOL_CALL_EMIT_TOKENS"
                    )
                    profile_tokens(
                        json.dumps(tool_result),
                        response.id,
                        model,
                        "TOOL_RESULT_TOKENS"
                    )
                    
            context_id = context_cache.update_context(
                followup.id,
                user_query,
                model,
                followup.model_dump()
            )
            
            if PROFILER:
                profile_tokens(json.dumps(followup.model_dump()), followup.id, model, "FOLLOWUP_OUTPUT_TOKENS")

            # summary checkpoint if we've accumulated TURNS worth of turns
            summary_context_id = get_summary_context_id()

            if summary_context_id is None or context_id - TURNS >= summary_context_id:

                summary_start_time = perf_counter()

                summary_response = create_summary(TURNS)

                summary_end_time = perf_counter()

                if summary_response is not None:
                    write_summary(
                        llm_response_id=followup.id,
                        model=model,
                        summary=summary_response,
                        through_context_id=context_id,
                    )
                    if PROFILER:
                        profile_tokens(json.dumps(summary_response), followup.id, model, "SUMMARY_UPDATE_TOKENS")

            # write timing metrics
            end_time = perf_counter()

            total_time_ms = int((end_time - start_time) * 1000)

            llm_ms = (
                int((llm_end_time - llm_start_time) * 1000)
                if llm_start_time is not None and llm_end_time is not None
                else None
            )

            tool_ms = (
                int((tool_end_time - tool_start_time) * 1000)
                if tool_start_time is not None and tool_end_time is not None 
                else None
            )

            tool_followup_ms = (
                int((tool_followup_end_time - tool_followup_start_time) * 1000)
                if tool_followup_start_time is not None and tool_followup_end_time is not None 
                else None
            )

            summary_ms = (
                int((summary_end_time - summary_start_time) * 1000)
                if summary_start_time is not None and summary_end_time is not None 
                else None
            )

            try:
                write_llm_timing(
                    followup.id, 
                    model, 
                    "tool_call", 
                    True, 
                    total_time_ms, 
                    llm_ms, 
                    tool_ms, 
                    tool_followup_ms, 
                    summary_ms,
                )
            except Exception as e:
              print(f"TIMING METRIC WRITE FAILURE: {e}")

            return followup.output_text

    context_id = context_cache.update_context(
        response.id,
        user_query,
        model,
        response.model_dump()
    )
   
    if PROFILER:
        profile_tokens(json.dumps(response.model_dump()), response.id, model, "RESPONSE_OUTPUT_TOKENS")

    # summary checkpoint if we've accumulated TURNS worth of turns
    summary_context_id = get_summary_context_id()

    if summary_context_id is None or context_id - TURNS >= summary_context_id:

        summary_start_time = perf_counter()

        summary_response = create_summary(TURNS)

        summary_end_time = perf_counter()

        if summary_response is not None:
            write_summary(
                llm_response_id=response.id,
                model=model,
                summary=summary_response,
                through_context_id=context_id,
            )
            if PROFILER:
                profile_tokens(json.dumps(summary_response), response.id, model, "SUMMARY_UPDATE_TOKENS")

    # write timing metrics
    end_time = perf_counter()

    total_time_ms = int((end_time - start_time) * 1000)

    llm_ms = (
        int((llm_end_time - llm_start_time) * 1000)
        if llm_start_time is not None and llm_end_time is not None
        else None
    )

    tool_ms = (
        int((tool_end_time - tool_start_time) * 1000)
        if tool_start_time is not None and tool_end_time is not None 
        else None
    )

    tool_followup_ms = (
        int((tool_followup_end_time - tool_followup_start_time) * 1000)
        if tool_followup_start_time is not None and tool_followup_end_time is not None 
        else None
    )

    summary_ms = (
        int((summary_end_time - summary_start_time) * 1000)
        if summary_start_time is not None and summary_end_time is not None 
        else None
    )

    try:
        write_llm_timing(
            response.id, 
            model, 
            "standard", 
            False, 
            total_time_ms, 
            llm_ms, 
            tool_ms, 
            tool_followup_ms, 
            summary_ms,
        )
    except Exception as e:
        print(f"TIMING METRIC WRITE FAILURE: {e}")

    return response.output_text
