from fastapi import FastAPI
from .routers import (
    webhook, user
)


app = FastAPI()

@app.get("/")
def home():
    return {"status": "ok"}

app.include_router(webhook.router)
app.include_router(user.router)