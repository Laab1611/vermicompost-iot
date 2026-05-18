#!/usr/bin/env sh
set -eu

cert_dir="${1:-.certs}"
mkdir -p "$cert_dir"

openssl req \
  -x509 \
  -nodes \
  -newkey rsa:2048 \
  -sha256 \
  -days 825 \
  -keyout "$cert_dir/localhost.key" \
  -out "$cert_dir/localhost.crt" \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$cert_dir/localhost.key"
chmod 644 "$cert_dir/localhost.crt"
