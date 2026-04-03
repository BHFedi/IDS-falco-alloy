# =========================
# BUILD STAGE - Nginx with HTTP/3 (QUIC) + BoringSSL
# =========================
FROM alpine:3.21 AS builder

ARG NGINX_VERSION=1.27.3
# Use a recent BoringSSL commit known to work well (update if needed)
ARG BORINGSSL_VERSION=origin/master

RUN apk add --no-cache \
    build-base \
    cmake \
    git \
    perl \
    linux-headers \
    pcre2-dev \
    zlib-dev \
    openssl-dev \
    curl

WORKDIR /build

# -------------------------
# Build BoringSSL
# -------------------------
RUN git clone https://boringssl.googlesource.com/boringssl.git && \
    cd boringssl && \
    git checkout ${BORINGSSL_VERSION} && \
    mkdir build && cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release .. && \
    make -j$(nproc)

# -------------------------
# Download and build Nginx with HTTP/3
# -------------------------
RUN curl -LO https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz && \
    tar -xzf nginx-${NGINX_VERSION}.tar.gz

WORKDIR /build/nginx-${NGINX_VERSION}

RUN ./configure \
    --prefix=/etc/nginx \
    --sbin-path=/usr/sbin/nginx \
    --modules-path=/usr/lib/nginx/modules \
    --conf-path=/etc/nginx/nginx.conf \
    --error-log-path=/var/log/nginx/error.log \
    --http-log-path=/var/log/nginx/access.log \
    --pid-path=/var/run/nginx.pid \
    --lock-path=/var/run/nginx.lock \
    --with-http_ssl_module \
    --with-http_v2_module \
    --with-http_v3_module \
    --with-stream \
    --with-stream_ssl_module \
    --with-threads \
    --with-file-aio \
    --with-http_realip_module \
    --with-http_gzip_static_module \
    --with-http_stub_status_module \
    --with-cc-opt="-I/build/boringssl/include -O2" \
    --with-ld-opt="-L/build/boringssl/build/ssl -L/build/boringssl/build/crypto -Wl,-rpath,/usr/local/lib"

RUN make -j$(nproc) && make install

# =========================
# RUNTIME STAGE - Minimal Alpine
# =========================
FROM alpine:3.21

# Runtime dependencies
RUN apk add --no-cache \
    ca-certificates \
    libstdc++ \
    pcre2 \
    zlib

# Copy built Nginx binary and config skeleton
COPY --from=builder /usr/sbin/nginx /usr/sbin/nginx
COPY --from=builder /etc/nginx /etc/nginx

# Create required directories
RUN mkdir -p /var/log/nginx /var/cache/nginx /etc/nginx/conf.d /etc/nginx/ssl \
    && chown -R nobody:nobody /var/log/nginx /var/cache/nginx /etc/nginx

# Expose both TCP and UDP on 443 for HTTP/3
EXPOSE 80/tcp
EXPOSE 443/tcp
EXPOSE 443/udp

STOPSIGNAL SIGQUIT

# Run as non-root (recommended)
USER nobody

CMD ["nginx", "-g", "daemon off;"]
