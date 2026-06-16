FROM python:3.12-slim

WORKDIR /app

# Сначала только requirements — кэшируется отдельным слоем
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код не копируем — монтируется через volume
CMD ["python", "main.py"]
