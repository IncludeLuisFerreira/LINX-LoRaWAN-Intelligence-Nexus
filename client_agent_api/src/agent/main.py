from fastapi import FastAPI

app = FastAPI(title="LINX Client Agent API")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
