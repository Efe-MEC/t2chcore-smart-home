FROM debian:trixie-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV LD_LIBRARY_PATH=/opt/llama/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3t64 \
    libopenblas0-pthread \
    libgfortran5 \
    libgomp1 \
    libstdc++6 \
    libgcc-s1 \
    zlib1g \
    libzstd1 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/llama/bin

EXPOSE 8081

ENTRYPOINT ["/opt/llama/bin/llama-server"]
