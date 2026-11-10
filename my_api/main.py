import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# 로컬에선 .env를 읽고, Railway에선 Variables가 이미 들어 있음
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SECRET_KEY = os.environ["SUPABASE_SECRET_KEY"]

# ─────────────── CORS (허용할 프론트 주소) ───────────────
# FRONT_ORIGINS 환경변수에 쉼표로 구분해 적는다.
#   Railway:  FRONT_ORIGINS=https://my-shop.vercel.app
#   로컬:     FRONT_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
# 규칙: "*" 금지, 경로 없이 origin만, 운영은 https만 (http는 localhost만 허용).
_ORIGIN_RE = re.compile(r"^https?://[A-Za-z0-9.-]+(:\d{1,5})?$")
_LOCAL_HTTP_RE = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d{1,5})?$")


def load_origins(raw: str) -> list[str]:
    origins = []
    for o in raw.split(","):
        o = o.strip().rstrip("/")
        if not o:
            continue
        if o == "*" or not _ORIGIN_RE.match(o):
            raise RuntimeError(f"FRONT_ORIGINS 값이 올바르지 않습니다: {o!r}")
        if o.startswith("http://") and not _LOCAL_HTTP_RE.match(o):
            raise RuntimeError(f"운영 origin은 https여야 합니다: {o!r}")
        origins.append(o)
    return origins


FRONT_ORIGINS = load_origins(os.getenv("FRONT_ORIGINS", ""))
if not FRONT_ORIGINS:
    print("WARNING: FRONT_ORIGINS가 비어 있어 모든 브라우저 요청이 차단됩니다.")

sb = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

# ENV=production 이면 /docs, /redoc, /openapi.json 을 숨겨 API 구조 노출을 줄인다.
IS_PROD = os.getenv("ENV", "").lower() == "production"
app = FastAPI(
    title="my-api",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONT_ORIGINS,          # 목록에 있는 주소만 허용 (와일드카드 X)
    allow_credentials=False,              # 쿠키/인증정보 미사용 → 꺼서 공격면 축소
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
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


# ─────────────── 장바구니 ───────────────
# 로그인이 없으므로 브라우저가 만든 익명 cart_id(UUID)로 장바구니를 구분한다.
CART_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def valid_cart_id(cart_id: str) -> str:
    if not CART_ID_RE.match(cart_id):
        raise HTTPException(status_code=400, detail="invalid cart_id")
    return cart_id


class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=99)


class QuantityIn(BaseModel):
    quantity: int = Field(ge=0, le=99)  # 0이면 삭제


def read_cart(cart_id: str) -> dict:
    res = (
        sb.table("cart_items")
        .select("product_id, quantity, products(name, price, emoji)")
        .eq("cart_id", cart_id)
        .order("created_at")
        .execute()
    )
    items = []
    for row in res.data:
        p = row["products"]
        items.append(
            {
                "product_id": row["product_id"],
                "name": p["name"],
                "emoji": p["emoji"],
                "price": p["price"],
                "quantity": row["quantity"],
                "subtotal": p["price"] * row["quantity"],
            }
        )
    return {
        "items": items,
        "count": sum(i["quantity"] for i in items),
        "total": sum(i["subtotal"] for i in items),
    }


@app.get("/products")
def list_products():
    res = sb.table("products").select("*").order("id").execute()
    return res.data


@app.get("/cart/{cart_id}")
def get_cart(cart_id: str):
    return read_cart(valid_cart_id(cart_id))


@app.post("/cart/{cart_id}/items")
def add_to_cart(cart_id: str, body: CartItemIn):
    valid_cart_id(cart_id)
    if not sb.table("products").select("id").eq("id", body.product_id).execute().data:
        raise HTTPException(status_code=404, detail="product not found")
    cur = (
        sb.table("cart_items")
        .select("quantity")
        .eq("cart_id", cart_id)
        .eq("product_id", body.product_id)
        .execute()
        .data
    )
    qty = min((cur[0]["quantity"] if cur else 0) + body.quantity, 99)
    sb.table("cart_items").upsert(
        {"cart_id": cart_id, "product_id": body.product_id, "quantity": qty},
        on_conflict="cart_id,product_id",
    ).execute()
    return read_cart(cart_id)


@app.put("/cart/{cart_id}/items/{product_id}")
def set_quantity(cart_id: str, product_id: int, body: QuantityIn):
    valid_cart_id(cart_id)
    if body.quantity == 0:
        sb.table("cart_items").delete().eq("cart_id", cart_id).eq(
            "product_id", product_id
        ).execute()
    else:
        res = (
            sb.table("cart_items")
            .update({"quantity": body.quantity})
            .eq("cart_id", cart_id)
            .eq("product_id", product_id)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="item not in cart")
    return read_cart(cart_id)


@app.delete("/cart/{cart_id}/items/{product_id}")
def remove_item(cart_id: str, product_id: int):
    valid_cart_id(cart_id)
    sb.table("cart_items").delete().eq("cart_id", cart_id).eq(
        "product_id", product_id
    ).execute()
    return read_cart(cart_id)


@app.delete("/cart/{cart_id}")
def clear_cart(cart_id: str):
    valid_cart_id(cart_id)
    sb.table("cart_items").delete().eq("cart_id", cart_id).execute()
    return read_cart(cart_id)
