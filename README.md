# IDS Falco-Alloy Collector

A security monitoring stack using **Falco** for intrusion detection and **Grafana Alloy** for log/metric collection.

These components send data securely to a remote monitoring stack via **mTLS enforced by NGINX**.

---

# Architecture

```
Falco  ──▶ HTTPS ──▶ NGINX (mTLS)
Alloy  ──▶ HTTPS ──▶ NGINX (mTLS)
```

* All traffic authenticated using client certificates

---

# Security Model

* Each agent has its own identity:

  * `CN=prod-falco`
  * `CN=prod-alloy`
* NGINX verifies certificates and routes traffic
* Unauthorized clients are rejected

---

# IMPORTANT: NO CERTS IN REPO

You MUST generate your own certificates.

```
*.key
*.crt
*.csr
```

---

# Certificate Setup

## 1. Create CA

```
openssl genrsa -out ca.key 4096

openssl req -x509 -new -nodes \
  -key ca.key -sha256 -days 365 \
  -out ca.crt -subj "/CN=healio-ca"
```

---

## 2. Alloy certificate

```
openssl genrsa -out alloy.key 2048

openssl req -new -key alloy.key -out alloy.csr \
  -subj "/CN=prod-alloy"

openssl x509 -req -in alloy.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out alloy.crt -days 365 -sha256
```

---

## 3. Falco certificate

```
openssl genrsa -out falco.key 2048

openssl req -new -key falco.key -out falco.csr \
  -subj "/CN=prod-falco"

openssl x509 -req -in falco.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out falco.crt -days 365 -sha256
```

---

#  Configuration

## Alloy

Set environment variable in docker-compose.yml:

```
- LOKI_URL=https://loki.example.com/loki/api/v1/push 
- PROMETHEUS_URL=https://prometheus.example.com/api/v1/write
```

---

## Falco

```
http_output:
  enabled: true
  url: "https://ingest.example.com/falco/"
```

---

# Deployment

```
docker compose up -d
```

---

# Validation

Test connectivity:

```
curl -vk https://ingest.example.com/loki/api/v1/labels \
  --cert alloy.crt \
  --key alloy.key \
  --cacert ca.crt
```

---

# Notes

* mTLS is enforced at the NGINX layer
* Falco does not fully support custom TLS client config
* Alloy provides full TLS control

---

# Disclaimer

This setup is intended for learning and controlled environments.

For production:

* Use a proper PKI
* Rotate certificates
* Add authentication layers

