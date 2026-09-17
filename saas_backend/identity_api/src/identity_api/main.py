from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from linx_shared.db.base import get_db
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from identity_api.routes.application import router as application_router
from identity_api.routes.tenant import router

app = FastAPI(title="LINX SAAS Backend")
BASE_DIR = Path(__file__).resolve().parent

# Mapeia a pasta de arquivos estáticos (CSS, JS, Imagens)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Configura o diretório onde estão os arquivos HTML
templates = Jinja2Templates(directory=BASE_DIR / "templates")


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


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # O parâmetro 'request' é obrigatório no contexto do Jinja2
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"titulo": "Página Inicial", "usuario": "Dev"},
    )


app.include_router(router)
app.include_router(application_router)
