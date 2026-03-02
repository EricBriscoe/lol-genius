FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -fsSL -o /usr/local/bin/dbmate https://github.com/amacneil/dbmate/releases/download/v2.22.0/dbmate-linux-amd64 \
    && chmod +x /usr/local/bin/dbmate \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .
RUN pip install --no-cache-dir -e .

USER appuser

ENV LOL_GENIUS_DOCKER=1
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["lol-genius"]
CMD ["crawl"]
