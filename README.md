# Vermicompost IoT Platform

Plataforma de monitoreo de vermicompostaje con arquitectura de microservicios, modelo DER en PostgreSQL, gateway Nginx y observabilidad con Prometheus/Grafana.

## Servicios y puertos

- api-gateway: 80
- telemetry-ingestion-service: 8001
- query-monitoring-service: 8002
- digital-twin-integration-service: 8003
- prometheus: 9090
- grafana: 3000

## Enrutamiento por Nginx

- /telemetry/* -> telemetry-ingestion-service
- /query/* -> query-monitoring-service
- /twins/* -> digital-twin-integration-service

Ejemplos por gateway:

```bash
curl http://localhost/telemetry/health
curl http://localhost/query/health
curl http://localhost/twins/health
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
- Actualizacion de ultima_lectura_recibida por nodo.

### query-monitoring-service

- Historicos y filtros por nodo/cama/tipo/rango.
- Estado actual por nodo y cama.
- Deteccion de nodos desconectados.
- Resumen global de monitoreo.

### digital-twin-integration-service

- Vistas agregadas para consumo de gemelo digital.
- Estado por nodo, por cama y overview global.

## Flujo del proyecto

1. Dispositivos IoT o clientes externos envian lecturas al gateway en /telemetry/api/v1/ingestion.
2. Nginx enruta la solicitud al telemetry-ingestion-service.
3. telemetry-ingestion-service valida reglas de dominio y clasifica invalidez automatica en ingestion.
4. Si la lectura es aceptada, se actualiza ultima_lectura_recibida del nodo correspondiente.
5. Toda lectura invalida se persiste en lectura_invalida con trazabilidad completa y datos crudos.
6. La clasificacion de error en ingestion incluye: timestamp_invalido, nodo_no_registrado, tipo_variable_no_soportado, payload_incompleto, valor_fuera_de_rango y error_desconocido.
7. query-monitoring-service consulta PostgreSQL para historicos, estados, lecturas invalidas (desde lectura_invalida) y nodos desconectados, expuestos por /query/.
8. digital-twin-integration-service consulta PostgreSQL para construir vistas de gemelo digital por nodo, por cama y globales, expuestas por /twins/.
9. Prometheus recolecta metricas de los servicios para observabilidad.
10. Grafana consume esas metricas para dashboards y seguimiento operativo.

## Levantar proyecto

1. Configura .env con DATABASE_URL.
2. Construye y levanta:

```bash
docker compose up --build -d
```

3. Smoke test:

```bash
curl http://localhost/telemetry/health
curl http://localhost/query/health
curl http://localhost/twins/health
```

## Pruebas recomendadas en local

```bash
python -m pytest telemetry-ingestion-service/tests
python -m pytest query-monitoring-service/tests
python -m pytest digital-twin-service/tests
python -m compileall telemetry-ingestion-service query-monitoring-service digital-twin-service
```

Hay pruebas unitarias dedicadas para los tres servicios.

## Escalabilidad con broker

El servicio de ingestion soporta dos modos configurables por entorno:

- `INGESTION_MODE=sync`: modo historico (request procesa y persiste en la misma llamada).
- `INGESTION_MODE=broker`: modo desacoplado (request encola mensaje y consumidor persiste asincrono).

Proveedor de broker configurable:

- `BROKER_PROVIDER=redis` como opcion recomendada para entorno limitado.
- `BROKER_PROVIDER=memory` para pruebas locales sin infraestructura externa.
<!-- - `BROKER_PROVIDER=rabbitmq` para integracion con RabbitMQ. -->

Controles de batch en modo broker:

- `BROKER_BATCH_SIZE=100`
- `BROKER_FLUSH_SECONDS=1.0`

Referencia tecnica completa:

- `docs/broker-escalabilidad-analisis.md`

## Documentacion por servicio

- telemetry-ingestion-service/README.md
- query-monitoring-service/README.md
- digital-twin-service/README.md
