from fastapi import FastAPI

app = FastAPI(title="LINX Tenant App Template")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
