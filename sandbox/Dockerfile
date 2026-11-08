FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1
RUN pip install pandas numpy matplotlib scipy
# No secrets, no extra tools. Runs as nobody with a read-only rootfs (set at `docker run`).
WORKDIR /sandbox
