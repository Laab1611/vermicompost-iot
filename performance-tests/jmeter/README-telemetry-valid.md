# JMeter: telemetría válida con p95 <= 5s

Este escenario valida el comportamiento normal de la ingesta de telemetría. Primero hace un warmup con endpoints de salud y luego empieza a enviar lecturas válidas al backend. El dataset nuevo simula 15 camas, y el perfil recomendado multiplica la carga hasta 180 lecturas por cama para cubrir la ventana de 30 minutos.

## Qué prueba

- Que el backend responda a salud antes de enviar carga.
- Que la ingesta válida entre por `POST /telemetry/api/v1/ingestion`.
- Que cada solicitud termine en menos de 5 segundos.
- Que el p95 del escenario se mantenga por debajo de 5000 ms bajo condiciones normales.

## Archivo principal

- [vermicompost-telemetry-valid.jmx](vermicompost-telemetry-valid.jmx)

## Datos de entrada

Usa el CSV:

- [performance-tests/jmeter/data/ingestion_valid_15_camas.csv](data/ingestion_valid_15_camas.csv)

Ese archivo contiene 15 filas semilla con `cama_id`, `nodo_id`, `tipo_variable_id`, `valor` y `fecha_medicion`.

## Perfil recomendado

Usa el perfil `telemetry-valid-15beds.properties` o uno equivalente con estos parámetros:

- `host=localhost`
- `port=80`
- `max_response_ms=5000`
- `ing_valid_threads=15`
- `ing_valid_ramp=30`
- `ing_valid_loops=180`

## Ejecución

Desde la raíz del repositorio:

```bash
jmeter -n -t performance-tests/jmeter/vermicompost-telemetry-valid.jmx \
  -q performance-tests/jmeter/profiles/telemetry-valid-15beds.properties \
  -l performance-tests/results/telemetry-valid/run.jtl \
  -e -o performance-tests/results/telemetry-valid/html-report
```

## Cómo leer el resultado

El escenario cumple si:

- No hay errores en la columna de estado del reporte.
- El `Response Time Percentile` p95 es menor o igual a 5000 ms.
- El porcentaje de errores es menor al 1%.

## Interpretación operativa

El warmup de salud no forma parte del SLA. Solo sirve para verificar que el backend está listo antes de empezar la carga real.

La parte relevante para el SLA es el sampler `POST /telemetry/api/v1/ingestion`.
