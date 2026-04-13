import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

API_BASE = "https://api-dev.stanfield-lab.com"
USER_ID = "16eac6d3-66eb-41a9-b78d-4923a0eb513b"

@router.get("/query-activities")
async def query_activities(
    activity_type: str = Query(...), detail_level: str = Query(...),start_date: str = Query(...),end_date: str = Query(...)):
    """
    Fetches a token efficient JSON obj containing the requested records
    """
    params = {
        "user_id": USER_ID,
        "detail_level": detail_level,
        "activity_type": activity_type,
        "start_date": start_date,
        "end_date": end_date,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{API_BASE}/query-activities", params=params)

        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Training Ledger API GET query-activities failed: {r.text}")

        data = r.json()

    return data

    
