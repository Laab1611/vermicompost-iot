# Plataforma IoT de Vermicompostaje

Plataforma de monitoreo de vermicompostaje con arquitectura de microservicios, modelo DER en PostgreSQL, gateway Nginx y observabilidad con Prometheus/Grafana.

## Servicios y puertos

- api-gateway HTTPS: https://localhost:8443
- telemetry-ingestion-service: interno en 8000
- query-monitoring-service: interno en 8000
- digital-twin-integration-service: interno en 8000
- prometheus: interno en 9090
- grafana: https://localhost:8443/grafana/

## Seguridad de API

- `telemetry`, `query` y `twins` requieren `Authorization: Bearer <token>`.
- Define `API_BEARER_TOKEN` en `.env` antes de levantar la pila.
- `health` sigue público para monitoreo.

## Enrutamiento por Nginx

- /telemetry/* -> telemetry-ingestion-service
- /query/* -> query-monitoring-service
- /twins/* -> digital-twin-integration-service

Ejemplos por gateway:

```bash
curl -k https://localhost:8443/telemetry/health
curl -k https://localhost:8443/query/health
curl -k https://localhost:8443/twins/health
```

## Modelo de datos (DER)

- cama_vermicompostaje(cama_id, nombre, ubicacion, latitud, longitud, created_at)
- nodo_sensor(nodo_id, cama_id, codigo_nodo, created_at, ultima_lectura_recibida)
- tipo_variable(tipo_variable_id, nombre, unidad_medida)
- lectura(lectura_id, nodo_id, tipo_variable_id, valor, fecha_medicion, fecha_recepcion)
- lectura_invalida(lectura_invalida_id, nodo_id, tipo_variable_id, valor_recibido, fecha_medicion, fecha_recepcion, tipo_error)

## Responsabilidad de cada servicio

### telemetry-ingestion-service

- Ingesta de lecturas.
- Validaciones de dominio y fechas.
- Persistencia de datos maestros y lecturas.
- Actualización de ultima_lectura_recibida por nodo.

### query-monitoring-service

- Historicos y filtros por nodo/cama/tipo/rango.
- Estado actual por nodo y cama.
- Deteccion de nodos desconectados.
- Resumen global de monitoreo.

### digital-twin-integration-service

- Vistas agregadas para consumo de gemelo digital.
- Estado por nodo, por cama y overview global.

## Flujo del proyecto

1. Dispositivos IoT o clientes externos envían lecturas al gateway en /telemetry/api/v1/ingestion con `Authorization: Bearer <token>`.
2. Nginx enruta la solicitud al telemetry-ingestion-service.
3. telemetry-ingestion-service valida reglas de dominio y clasifica invalidez automática en ingesta.
4. Si la lectura es aceptada, se actualiza ultima_lectura_recibida del nodo correspondiente.
5. Toda lectura inválida se persiste en lectura_invalida con trazabilidad completa y datos crudos.
6. La clasificación de error en ingesta incluye: timestamp_invalido, nodo_no_registrado, tipo_variable_no_soportado, payload_incompleto, valor_fuera_de_rango y error_desconocido.
7. query-monitoring-service consulta PostgreSQL para históricos, estados, lecturas inválidas (desde lectura_invalida) y nodos desconectados, expuestos por /query/.
8. digital-twin-integration-service consulta PostgreSQL para construir vistas de gemelo digital por nodo, por cama y globales, expuestas por /twins/.
9. Prometheus recolecta métricas de los servicios para observabilidad.
10. Grafana consume esas métricas para dashboards y seguimiento operativo.

## Levantar proyecto

1. Configura `.env` con `DATABASE_URL` y `API_BEARER_TOKEN`.
2. Construye y levanta. Compose provisiona el certificado local en `.certs/` automáticamente:

```bash
docker compose up --build -d
```

Si usas Podman, ejecuta el mismo archivo con el wrapper local:

```bash
source ~/Documents/code/py_venvs/podman_compose/bin/activate
podman-compose up --build -d
```

3. Smoke test:

```bash
curl -k https://localhost:8443/telemetry/health
curl -k https://localhost:8443/query/health
curl -k https://localhost:8443/twins/health
```

## Checklist de integración de observabilidad

Después de levantar el stack, validar:

1. Estado de servicios:
	- `telemetry-ingestion-service`, `query-monitoring-service`, `digital-twin-integration-service`, `prometheus` y `grafana` en estado `healthy`.
2. Prometheus interno:
	- Confirmar el contenedor `prometheus` en estado `healthy`.
	- Verificar desde Grafana que el datasource `Prometheus` está aprovisionado y que los dashboards cargan métricas.
3. Reglas de alertas cargadas:
	- Confirmar en los logs de Prometheus que los grupos `disponibilidad-servicios`, `rendimiento-api` e `ingestion-broker` cargan sin errores.
	- El UI de Prometheus no se expone públicamente.
4. Provisioning automático de Grafana:
	- Ingresar a `https://localhost:8443/grafana/`.
	- Verificar datasource `Prometheus` aprovisionado automáticamente.
   - Verificar el tablero `Vermicompost IoT - Observabilidad del Backend` en la carpeta `Observabilidad`.
5. Métricas nuevas de backend visibles:
	- Validar series `ingestion_broker_enqueue_total`, `ingestion_broker_processed_total`, `ingestion_broker_process_seconds`, `ingestion_redis_stream_length`, `ingestion_redis_pending_messages`, `ingestion_redis_consumer_lag`, `ingestion_batch_buffer_size`.
6. SLO de latencia:
	- Confirmar panel y alertas p95 para ingesta y consulta con umbral de 5000 ms.

## Pruebas recomendadas en local

```bash
python -m pytest telemetry-ingestion-service/tests
python -m pytest query-monitoring-service/tests
python -m pytest digital-twin-service/tests
python -m compileall telemetry-ingestion-service query-monitoring-service digital-twin-service
```

Hay pruebas unitarias dedicadas para los tres servicios.

## Pruebas de API

- Colección de Postman: `postman/vermicomposting.postman_collection.json`
- Usa `https://localhost:8443` y desactiva la verificación SSL local o importa `.certs/localhost.crt`.

## Escalabilidad con broker

El servicio de ingesta soporta dos modos configurables por entorno:

- `INGESTION_MODE=sync`: modo histórico (request procesa y persiste en la misma llamada).
- `INGESTION_MODE=broker`: modo desacoplado (request encola mensaje y consumidor persiste asíncrono).

Proveedor de broker configurable:

- `BROKER_PROVIDER=redis` como opción recomendada para entorno limitado.
- `BROKER_PROVIDER=memory` para pruebas locales sin infraestructura externa.

Controles de batch en modo broker:

- `BROKER_BATCH_SIZE=100`
- `BROKER_FLUSH_SECONDS=1.0`

Referencia técnica completa:

- `docs/broker-escalabilidad-analisis.md`

## Documentación por servicio

- telemetry-ingestion-service/README.md
- query-monitoring-service/README.md
- digital-twin-service/README.md
