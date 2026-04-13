from app.tools.query_activities import query_activities

async def request_tool(tool_name, args):
    """
    Tool dispatcher for the LLM via chat.py
    """

    if(tool_name == 'query_activities'):
        return await query_activities(**args)
    else:
        return f"Tool Request Failure: no such tool as {tool_name}"


