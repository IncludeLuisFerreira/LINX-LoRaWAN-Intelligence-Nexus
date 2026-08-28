from fastapi import FastAPI

app = FastAPI(title="LINX SAAS Backend")

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

