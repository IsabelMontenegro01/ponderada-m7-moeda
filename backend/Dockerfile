FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000
# o modelo NÃO fica dentro da imagem, ele chega pelo volume /models
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
