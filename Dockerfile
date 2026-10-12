FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make the startup script executable
RUN chmod +x entrypoint.sh

# Expose ONLY the Chainlit port to the outside world
EXPOSE 8001

# Run the startup script
CMD ["./entrypoint.sh"]