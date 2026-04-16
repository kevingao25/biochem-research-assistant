FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

# --no-cache-dir keeps the image smaller by not storing the pip download cache
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# --host 0.0.0.0 is required inside Docker so the server accepts connections from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
