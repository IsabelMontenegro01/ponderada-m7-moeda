FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY train.py .

# o CSV entra por volume em /data e o modelo sai por volume em /models
CMD ["python", "train.py"]  