FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY emg_mcp.py .

# Placeholders; set real values at run time (see docker-compose.example.yml).
ENV EMG_BRIDGE_URL=https://bridge.example.com \
    MCP_PUBLIC_HOST=mcp.example.com \
    PYTHONUNBUFFERED=1

EXPOSE 8000
USER nobody
CMD ["python", "emg_mcp.py"]
