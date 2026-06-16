FROM python:3.12-slim

WORKDIR /app

# Код не копируем — монтируется через volume
CMD ["python", "-u" "main.py"]
