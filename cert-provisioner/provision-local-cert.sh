#!/usr/bin/env sh
set -eu

cert_dir="${CERT_DIR:-/certs}"
cert_file="$cert_dir/localhost.crt"
key_file="$cert_dir/localhost.key"

mkdir -p "$cert_dir"

subject=""
if [ -s "$cert_file" ]; then
  subject="$(openssl x509 -in "$cert_file" -noout -subject -nameopt RFC2253 2>/dev/null || true)"
fi

needs_regen=0
if [ ! -s "$cert_file" ] || [ ! -s "$key_file" ]; then
  needs_regen=1
elif ! printf '%s' "$subject" | grep -q 'O=UAO'; then
  needs_regen=1
elif ! printf '%s' "$subject" | grep -q 'OU=BISITE Team EdgeAIoT'; then
  needs_regen=1
fi

if [ "$needs_regen" -eq 1 ]; then
  rm -f "$cert_file" "$key_file"
  openssl req \
    -x509 \
    -nodes \
    -newkey rsa:4096 \
    -sha256 \
    -days 365 \
    -keyout "$key_file" \
    -out "$cert_file" \
    -subj "/CN=localhost/O=UAO/OU=BISITE Team EdgeAIoT" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
  chmod 600 "$key_file"
  chmod 644 "$cert_file"
fi

if [ "${CERT_PROVISIONER_MODE:-serve}" = "serve" ]; then
  exec tail -f /dev/null
fi
