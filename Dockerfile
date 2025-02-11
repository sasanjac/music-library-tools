FROM ghcr.io/astral-sh/uv:python3.13-bookworm


COPY . /app
WORKDIR /app
RUN uv sync --frozen --no-dev && chmod 777 -R /app

VOLUME /data/import /data/export_electro /data/export_general /data/todo

CMD ["uv", "run", "--no-cache", "music-library-tools"]