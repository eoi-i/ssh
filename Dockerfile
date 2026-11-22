FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PORT=2222 \
    SSH_USER=terminal \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    sudo \
    python3 \
    ca-certificates \
    bash \
    coreutils \
    procps \
    iproute2 \
    iputils-ping \
    curl \
    wget \
    nano \
    vim-tiny \
    less \
    file \
    git \
    unzip \
    zip \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd

WORKDIR /opt/terminal
COPY main.py /opt/terminal/main.py
RUN chmod 755 /opt/terminal/main.py

EXPOSE 2222
STOPSIGNAL SIGTERM
CMD ["python3", "/opt/terminal/main.py"]
