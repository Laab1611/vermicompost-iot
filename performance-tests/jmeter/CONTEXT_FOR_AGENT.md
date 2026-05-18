# Contexto Del Proyecto Para Pruebas JMeter

## Objetivo de pruebas

Evaluar latencia, estabilidad y capacidad de respuesta del backend ante diferentes volumenes de trafico.

SLO funcional para backend en este proyecto:
- p95 de endpoints de ingestion y consulta menor o igual a 5000 ms.
- Codigos esperados estables bajo carga.

## Arquitectura relevante

Stack de backend y enrutamiento:
- API Gateway Nginx publica el backend en https://localhost:8443
- Telemetry Ingestion: /telemetry
- Query Monitoring: /query
- Digital Twin: /twins

Servicios de aplicacion:
- telemetry-ingestion-service (escritura y validacion)
- query-monitoring-service (consulta historica y estado)
- digital-twin-service (estado de twin)

Base de datos:
- PostgreSQL (via DATABASE_URL en variables de entorno)

## Endpoints clave para performance

Telemetry:
- GET /telemetry/health
- POST /telemetry/api/v1/ingestion
- GET /telemetry/api/v1/lecturas

Query:
- GET /query/health
- GET /query/api/v1/monitoring/summary
- GET /query/api/v1/lecturas/historico/nodo/{nodo_id}?limit={limit}
- GET /query/api/v1/lecturas/invalidas?limit={limit}
- GET /query/api/v1/estado/nodo/{nodo_id}?minutes={minutes}

Twins:
- GET /twins/health
- GET /twins/api/v1/twins/overview
- GET /twins/api/v1/twins?readings_limit={limit}

## Semantica de datos que impacta pruebas

- Toda lectura invalida se persiste en tabla lectura_invalida.
- valor_fuera_de_rango en backend significa valor no decimal, no umbral operativo.
- Umbrales de negocio operativos se manejan en Grafana, no en backend.
- Nodos pueden aparecer como desconectados segun ventana minutes en query service.

## Prerrequisitos de datos para carga

Antes de pruebas de volumen, garantizar datos maestros:
1. Crear al menos 1 cama.
2. Crear al menos 1 nodo asociado.
3. Crear al menos 1 tipo de variable.
4. Confirmar IDs existentes en base para CSV de JMeter.

Recomendado para volumen medio y alto:
- 10 nodos activos.
- 3 tipos de variable.
- Historico minimo de 1000 lecturas validas.
- Lecturas invalidas de muestra para endpoint invalidas.

## Matriz sugerida de escenarios

1. Latencia base (smoke)
- Threads: 5 a 10
- Ramp-up: 20 s
- Duracion: 2 a 5 min
- Objetivo: validar p95 y codigos esperados.

2. Estabilidad (soak)
- Threads: 20 a 40
- Ramp-up: 60 s
- Duracion: 20 a 30 min
- Objetivo: detectar degradacion, errores intermitentes y timeouts.

3. Volumen alto (stress controlado)
- Threads: 80 a 120
- Ramp-up: 120 s
- Duracion: 10 a 15 min
- Objetivo: punto de saturacion y comportamiento bajo presion.

## Metricas a recolectar

JMeter:
- p50, p90, p95, p99
- Throughput
- Error rate
- Active threads

Infra:
- CPU y memoria de contenedores
- latencia de base de datos
- disponibilidad de endpoints health

## Criterios de aceptacion sugeridos

- p95 <= 5000 ms en ingestion y consultas principales.
- Error rate < 1% para carga base y estabilidad.
- Sin caidas de servicios durante soak.
- Sin crecimiento sostenido anomalo de latencia en ventanas de 5 min.

## Comandos base para ejecutar plan

Ejemplo (CLI no GUI):

jmeter -n -t performance-tests/jmeter/vermicompost-backend.jmx \
  -q performance-tests/jmeter/profiles/smoke.properties \
  -l performance-tests/results/smoke/run.jtl \
  -e -o performance-tests/results/smoke/html-report

## Notas para el agente de performance

- Ejecutar pruebas por perfil: smoke, load, stress.
- Ajustar host, puerto e IDs de datasets antes de correr.
- Versionar resultados JTL y reporte HTML por corrida.
- Si se detecta p95 > 5 s, aislar por endpoint y repetir escenario focalizado.
