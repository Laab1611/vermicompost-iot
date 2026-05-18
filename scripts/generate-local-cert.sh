#!/usr/bin/env sh
set -eu

cert_dir="${1:-.certs}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

CERT_DIR="$cert_dir" CERT_PROVISIONER_MODE=oneshot sh "$script_dir/cert-provisioner/provision-local-cert.sh"
