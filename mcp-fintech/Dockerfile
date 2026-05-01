FROM python:3.14-slim

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

COPY mcp-fintech/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY mcp-fintech/server.py .

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

CMD ["python", "server.py"]
