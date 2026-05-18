#!/usr/bin/env sh
set -eu

cert_dir="${CERT_DIR:-/certs}"
cert_file="$cert_dir/localhost.crt"
key_file="$cert_dir/localhost.key"
san_file="$cert_dir/localhost.san"
subject_alt_name="${CERT_SUBJECT_ALT_NAME:-DNS:localhost,IP:127.0.0.1}"

mkdir -p "$cert_dir"

subject=""
if [ -s "$cert_file" ]; then
  subject="$(openssl x509 -in "$cert_file" -noout -subject -nameopt RFC2253 2>/dev/null || true)"
fi

stored_subject_alt_name=""
if [ -s "$san_file" ]; then
  IFS= read -r stored_subject_alt_name < "$san_file" || true
fi

needs_regen=0
if [ ! -s "$cert_file" ] || [ ! -s "$key_file" ]; then
  needs_regen=1
elif ! printf '%s' "$subject" | grep -q 'O=UAO'; then
  needs_regen=1
elif ! printf '%s' "$subject" | grep -q 'OU=BISITE Team EdgeAIoT'; then
  needs_regen=1
elif [ "$stored_subject_alt_name" != "$subject_alt_name" ]; then
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
    -addext "subjectAltName=$subject_alt_name"
  chmod 600 "$key_file"
  chmod 644 "$cert_file"
  printf '%s\n' "$subject_alt_name" > "$san_file"
  chmod 644 "$san_file"
fi

if [ "${CERT_PROVISIONER_MODE:-serve}" = "serve" ]; then
  exec tail -f /dev/null
fi
