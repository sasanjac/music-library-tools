FROM ghcr.io/astral-sh/uv:python3.13-bookworm


COPY . /app
WORKDIR /app
RUN  uv sync --all-extras --no-dev

VOLUME /data/import /data/export_electro /data/export_general /data/todo

CMD ["uv", "run", "music-library-tools"]