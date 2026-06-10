FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY catalog ./catalog
COPY research_hub ./research_hub

EXPOSE 3030

CMD ["python3", "-m", "research_hub", "--host", "0.0.0.0", "--port", "3030"]
