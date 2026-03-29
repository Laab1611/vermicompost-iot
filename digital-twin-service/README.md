# Digital Twin Integration Service

Servicio de lectura para proyeccion de estado de gemelo digital.

Puerto local: 8003
Base URL por gateway: http://localhost/twins

## Endpoints

- GET /health
- GET /api/v1/twins/overview
- GET /api/v1/twins?readings_limit=
- GET /api/v1/twins/camas/{cama_id}?readings_limit=
- GET /api/v1/twins/nodos/{nodo_id}?readings_limit=

## Validaciones de entrada

- readings_limit: 1..1000

## Errores HTTP esperados

- 400: parametro invalido
- 404: nodo/cama no existe
- 500: error de persistencia

## Curl de validacion

### Casos exitosos

```bash
curl http://localhost/twins/health
curl http://localhost/twins/api/v1/twins/overview
curl "http://localhost/twins/api/v1/twins?readings_limit=200"
curl "http://localhost/twins/api/v1/twins/camas/1?readings_limit=200"
curl "http://localhost/twins/api/v1/twins/nodos/1?readings_limit=200"
```

### Casos de error controlado

```bash
# readings_limit invalido -> 422 por validacion de FastAPI
curl "http://localhost/twins/api/v1/twins?readings_limit=0"

# cama no existe -> 404
curl "http://localhost/twins/api/v1/twins/camas/9999?readings_limit=200"

# nodo no existe -> 404
curl "http://localhost/twins/api/v1/twins/nodos/9999?readings_limit=200"
```