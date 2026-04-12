FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir --break-system-packages -r https://raw.githubusercontent.com/acese-dev/skill-fragment-engine/main/requirements.txt || \
    pip install --no-cache-dir --break-system-packages \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    sqlalchemy[asyncio]>=2.0.25 \
    asyncpg>=0.29.0 \
    faiss-cpu>=1.7.4 \
    numpy>=1.26.0 \
    redis>=5.0.0 \
    httpx>=0.26.0 \
    aiohttp>=3.9.0 \
    python-dotenv>=1.0.0 \
    pyyaml>=6.0.0 \
    structlog>=24.1.0 \
    tenacity>=8.2.0

COPY src/ ./src/
COPY pyproject.toml .

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "skill_fragment_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]