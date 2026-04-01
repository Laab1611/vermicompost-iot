#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f /etc/grafana/provisioning/datasources/prometheus.yml.tpl ]]; then
  echo "Passthrough mode: no template found, using existing YAML"
else
  echo "Renderizando plantilla de Datasource Grafana con variables de entorno..."
  envsubst < /etc/grafana/provisioning/datasources/prometheus.yml.tpl > /etc/grafana/provisioning/datasources/prometheus.yml
fi

exec /run.sh --homepath=/usr/share/grafana
