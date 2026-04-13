from fastapi import FastAPI
from fastapi import Response

from app.routes.chat import chat_router
from app.tools.query_activities import router as query_activities

app = FastAPI()
app.include_router(chat_router)
app.include_router(query_activities)

@app.get("/health")
def health():
  return {"status": "ok"}

