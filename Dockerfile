# Indian Markets Analytics Platform: web page + MCP server, with engine C (Rust) compiled in.
# The data is NOT in the image (it is not published). Mount your local data folder:
#   docker build -t imap .
#   docker run --rm -p 127.0.0.1:8765:8765 -v "$PWD/data:/app/data" imap            # web page
#   docker run --rm -i -v "$PWD/data:/app/data" imap python mcp_server.py          # MCP over stdio
# Always publish to 127.0.0.1 as above; the app is single-user and local.

FROM rust:1-slim AS engine_c
RUN pip3 --version >/dev/null 2>&1 || (apt-get update && apt-get install -y --no-install-recommends python3 python3-pip python3-venv && rm -rf /var/lib/apt/lists/*)
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir "maturin>=1.7,<2"
COPY engine_c /src/engine_c
WORKDIR /src/engine_c
RUN cargo test --release --no-default-features && /venv/bin/maturin build --release --out /wheels

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 IMAP_IN_CONTAINER=1 IMAP_REQUIRE_C=1
RUN useradd --create-home --uid 10001 imap
WORKDIR /app
COPY requirements-lock.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements-lock.txt
COPY --from=engine_c /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
COPY src ./src
COPY serve.py mcp_server.py macro.py refresh.py prices.py pyproject.toml ./
COPY tests ./tests
USER imap
EXPOSE 8765
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen(u.Request('http://127.0.0.1:8765/', headers={'Host':'127.0.0.1'}), timeout=4)"
CMD ["python", "serve.py"]
