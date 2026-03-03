FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY main.py .

# config/queries.yaml is expected to be mounted at /app/config/queries.yaml
# Secrets are provided via JIRA_API_TOKEN and SLACK_BOT_TOKEN env vars

CMD ["python", "main.py", "schedule"]
