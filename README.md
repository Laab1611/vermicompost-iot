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
- lectura(lectura_id, nodo_id, tipo_variable_id, valor, fecha_medicion, fecha_recepcion, es_valida, motivo_invalidacion)

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
5. Las ingestas invalidas por timestamp se persisten en lectura con motivo_invalidacion.
6. Las ingestas invalidas por payload_incompleto, nodo_no_registrado o tipo_variable_no_soportado se aceptan y reportan motivo, pero no se persisten en lectura por restricciones del DER.
7. query-monitoring-service consulta PostgreSQL para historicos, estados, lecturas invalidas persistidas y nodos desconectados, expuestos por /query/.
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

## Documentacion por servicio

- telemetry-ingestion-service/README.md
- query-monitoring-service/README.md
- digital-twin-service/README.md
