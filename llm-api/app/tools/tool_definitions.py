tools = [
  {
    "type": "function",
    "name": "query_activities",
    "description": (
      "Retrieve the athlete's recorded training and journal data for a specific date range. "
      "Use this tool when the user asks about workouts, activity history, mileage, elevation, "
      "training load, recovery context, journal entries, or comparisons across dates. "
      "This tool is the source of truth for athlete-specific history. "
      "Do not answer from memory when the user is asking about recorded training data that should be retrieved."
    ),
    "parameters": {
      "type": "object",
      "properties": {
        "activity_type": {
          "type": "string",
          "enum": ["endurance", "strength", "journal", "all"],
          "description": (
            "Which type of data to retrieve. "
            "Use 'endurance' for runs, rides, and other endurance training. "
            "Use 'strength' for lifting or strength sessions. "
            "Use 'journal' for daily journal or recovery entries. "
            "Use 'all' only when the user is asking for a combined view across multiple data types in the same date range."
          )
        },
        "detail_level": {
          "type": "string",
          "enum": ["summary", "metrics", "detail"],
          "description": (
            "How much information to return. "
            "Use 'summary' for simple recaps, totals, counts, or lists. "
            "Use 'metrics' for workout-level performance analysis such as pace, heart rate, power, cadence, zones, load, or comparisons across workouts. "
            "Use 'detail' for split-level, segment-level, lap-level, interval-level, or mile-by-mile inspection. "
            "If the user asks for splits, segments, laps, interval structure, or per-mile detail, use 'detail'. "
            "Journal entries always return full journal text/details regardless of detail_level."
          )
        },
        "start_date": {
          "type": "string",
          "description": (
            "Start date in YYYY-MM-DD format, inclusive. "
            "Use only this field for the start of the date range. "
            "Do not use start_time or any other alternate field name."
          )
        },
        "end_date": {
          "type": "string",
          "description": (
            "End date in YYYY-MM-DD format, inclusive. "
            "Use only this field for the end of the date range. "
            "Do not use end_time or any other alternate field name."
          )
        }
      },
      "required": ["activity_type", "detail_level", "start_date", "end_date"],
      "additionalProperties": False
    }
  }
]
