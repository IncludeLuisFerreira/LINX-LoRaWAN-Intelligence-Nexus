FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pagina.py .

EXPOSE 5000

CMD ["python", "pagina.py"]
