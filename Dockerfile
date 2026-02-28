FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

ENV LOL_GENIUS_DOCKER=1
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["lol-genius"]
CMD ["crawl"]
