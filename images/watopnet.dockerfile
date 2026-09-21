# Builder stage
FROM python:3.12.8-alpine3.21 AS builder

RUN apk --no-cache add \
    curl \
    bash \
    alpine-sdk \
    libffi-dev \
    libsodium \
    libsodium-dev

SHELL ["/bin/bash", "-c"]

# Rust is required to build the blake3 dependency of keri
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /watopnet

RUN python -m venv venv
ENV PATH=/watopnet/venv/bin:${PATH}
RUN pip install --upgrade pip

COPY pyproject.toml README.md LICENSE constraints.txt ./
COPY src/ src/

# constraints.txt pins every transitive dependency; its header has the command that regenerates it
RUN . "$HOME/.cargo/env" && pip install -c constraints.txt .

# Runtime stage
FROM python:3.12.8-alpine3.21

# gcc is not cruft: on musl, ctypes.util.find_library falls back to invoking the compiler
# to resolve a library name, and without it pysodium cannot find libsodium at runtime.
RUN apk --no-cache add \
    bash \
    curl \
    libsodium \
    libsodium-dev \
    gcc

WORKDIR /watopnet

COPY --from=builder /watopnet/venv /watopnet/venv
ENV PATH=/watopnet/venv/bin:${PATH}

# 7632 is the watcher endpoint that witnesses and validators reach.
# 7631 is the provisioning API: reachable on the container network so an operator or
# init job can call it, but it must never be published to a host or ingress.
EXPOSE 7632

# --config-file is accepted by the CLI and never reaches setup(), so it is omitted
# deliberately.  keripy's Configer resolves <config-dir>/keri/cf/main/watopnet.json.
ENTRYPOINT ["watopnet"]
CMD ["start", \
     "--config-dir", "/watopnet/config", \
     "--host", "0.0.0.0", "--http", "7632", \
     "--boothost", "0.0.0.0", "--bootport", "7631"]
