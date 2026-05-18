# Digital Twin Integration Service

Servicio de lectura para proyeccion de estado de gemelo digital.

Puerto local: interno en 8000
Base URL por gateway: https://localhost:8443/twins

## Endpoints

- GET /health
- GET /api/v1/twins/overview
- GET /api/v1/twins?readings_limit=
- GET /api/v1/twins/camas/{cama_id}?readings_limit=
- GET /api/v1/twins/nodos/{nodo_id}?readings_limit=

## Nota de overview

- total_camas y total_nodos se calculan desde tablas maestras.
- lecturas_validas se calcula desde lectura.
- lecturas_invalidas se calcula desde lectura_invalida.

## Validaciones de entrada

- readings_limit: 1..1000

## Errores HTTP esperados

- 400: parametro invalido
- 404: nodo/cama no existe
- 500: error de persistencia

## Curl de validacion

### Casos exitosos

```bash
curl -k https://localhost:8443/twins/health
curl -k https://localhost:8443/twins/api/v1/twins/overview
curl -k "https://localhost:8443/twins/api/v1/twins?readings_limit=200"
curl -k "https://localhost:8443/twins/api/v1/twins/camas/1?readings_limit=200"
curl -k "https://localhost:8443/twins/api/v1/twins/nodos/1?readings_limit=200"
```

### Casos de error controlado

```bash
# readings_limit invalido -> 422 por validacion de FastAPI
curl -k "https://localhost:8443/twins/api/v1/twins?readings_limit=0"

# cama no existe -> 404
curl -k "https://localhost:8443/twins/api/v1/twins/camas/9999?readings_limit=200"

# nodo no existe -> 404
curl -k "https://localhost:8443/twins/api/v1/twins/nodos/9999?readings_limit=200"
```

## Pruebas locales

```bash
python -m pytest digital-twin-service/tests
python -m compileall app
```

La suite incluye casos positivos y negativos para estados twin, limites de consulta y overview.
