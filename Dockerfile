# Daemonbot — MR SYCO (@Sycosmile)
FROM python:3.12-slim

WORKDIR /app

# System deps: gcc needed by some wheels on slim images, removed after install
# to keep the final image small.
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data

# Persist leaderboard/conviction/alerts data across container restarts by
# mounting a volume here: docker run -v daemonbot_data:/app/data ...
VOLUME ["/app/data"]

CMD ["python", "main.py"]
