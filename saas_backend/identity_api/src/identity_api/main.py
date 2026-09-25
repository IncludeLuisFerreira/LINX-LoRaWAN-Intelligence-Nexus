from fastapi import Depends, FastAPI, Response, status
from linx_shared.db.base import get_db
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from identity_api.routes.application import router as application_router
from identity_api.routes.tenant import router

app = FastAPI(title="LINX SAAS Backend")


@app.get("/health")
def health(response: Response, db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except SQLAlchemyError:
        db_ok = False

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
    }


app.include_router(router)
app.include_router(application_router)
