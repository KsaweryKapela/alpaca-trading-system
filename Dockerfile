FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY trading/ ./trading/
COPY live_trader.py .

CMD ["python", "-u", "live_trader.py"]
