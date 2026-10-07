FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app/services/api
COPY services/api/requirements-lock.txt ./requirements-lock.txt
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY services/api/app ./app
COPY services/api/scripts/start_server.py ./scripts/start_server.py
COPY services/api/scripts/__init__.py ./scripts/__init__.py
COPY ml/creditiq_ml /app/ml/creditiq_ml
COPY ml/requirements-lock.txt /app/ml/requirements-lock.txt
COPY .deployment-assets/ml /app/ml
RUN (getent group 1000 >/dev/null || groupadd --gid 1000 render-secrets) && useradd --uid 10001 --create-home --groups 1000 creditiq
ENV PYTHONPATH=/app/services/api PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/matplotlib PORT=8000
USER creditiq
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health/ready',timeout=4)"
CMD ["python", "-m", "scripts.start_server"]
