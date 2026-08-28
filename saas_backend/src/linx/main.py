from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="LINX SAAS Backend")

BASE_DIR = Path(__file__).resolve().parent

# Mapeia a pasta de arquivos estáticos (CSS, JS, Imagens)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Configura o diretório onde estão os arquivos HTML
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # O parâmetro 'request' é obrigatório no contexto do Jinja2
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"titulo": "Página Inicial", "usuario": "Dev"},
    )
