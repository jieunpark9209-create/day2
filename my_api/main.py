import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# 로컬에선 .env를 읽고, Railway에선 Variables가 이미 들어 있음
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]
FRONT_ORIGINS = [
    o.strip() for o in os.getenv("FRONT_ORIGINS", "").split(",") if o.strip()
]

sb = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

app = FastAPI(title="my-api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONT_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/v")
def health():
    return {"s":"100", "t":"200"}
    



class MessageIn(BaseModel):
    content: str


@app.get("/messages")
def list_messages():
    res = sb.table("messages").select("*").order("id", desc=True).limit(50).execute()
    return res.data


@app.post("/messages")
def create_message(body: MessageIn):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is empty")
    res = sb.table("messages").insert({"content": content}).execute()
    return res.data[0]
