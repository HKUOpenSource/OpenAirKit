ARG BASE_IMAGE=ubuntu@sha256:95fa486768020359141f1318720f43e7982ef926c792891d984aef9aaf05e7ea
FROM ${BASE_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ninja-build meson cmake flex bison git pkg-config \
    python3 ca-certificates netbase libsctp-dev libgnutls28-dev libgcrypt-dev \
    libssl-dev libidn-dev libmongoc-dev libbson-dev libyaml-dev libnghttp2-dev \
    libmicrohttpd-dev libcurl4-gnutls-dev libtins-dev libtalloc-dev \
    iproute2 iputils-ping iperf3 && \
    mkdir -p /opt/aoc-evidence && \
    dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > /opt/aoc-evidence/packages.tsv && \
    rm -rf /var/lib/apt/lists/*
COPY source /src/open5gs
COPY sources.lock.json /opt/aoc-evidence/sources.lock.json
WORKDIR /src/open5gs
RUN meson setup build --prefix=/opt/open5gs --libdir=lib \
    --buildtype=release --wrap-mode=nodownload && \
    ninja -C build -j2 && \
    meson test -C build --suite unit --num-processes 1 --print-errorlogs && \
    ninja -C build install && \
    cp build/meson-logs/testlog.json /opt/aoc-evidence/unit-tests.jsonl
ENV LD_LIBRARY_PATH=/opt/open5gs/lib:/opt/open5gs/lib/aarch64-linux-gnu
COPY smoke_inside.py /opt/aoc-tools/smoke_inside.py
LABEL org.opencontainers.image.source="https://github.com/open5gs/open5gs" \
      org.opencontainers.image.revision="157f611a530e292e40ec50f9d23f0ef5d4fcd6a6" \
      org.opencontainers.image.version="2.8.0" \
      org.agentic-ocudu.role="open5gs-validation"
CMD ["python3", "/opt/aoc-tools/smoke_inside.py"]
