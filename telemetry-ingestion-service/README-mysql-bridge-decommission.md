# Retiro del puente provisional MySQL -> broker

Este documento explica qué eliminar cuando ya no sea necesario el puente provisional que lee la tabla legacy de MySQL y publica al broker.

El objetivo es retirar solo la capa temporal de sincronización desde MySQL. No elimina el flujo original del backend ni el worker que consume del broker para persistir en PostgreSQL, salvo que también decidas desactivar ese pipeline por completo.

## Qué se puede eliminar

### 1. El worker nuevo de sincronización MySQL

Eliminar el archivo:

- [telemetry-ingestion-service/app/mysql_worker.py](../telemetry-ingestion-service/app/mysql_worker.py)

Motivo:

- Este archivo contiene la lógica provisional que lee MySQL, hace el mapeo de filas anchas a lecturas normalizadas y publica al broker.
- Cuando el origen directo de sensores al backend ya funcione, esta capa deja de ser necesaria.

### 2. La dependencia de MySQL

Eliminar de [telemetry-ingestion-service/requirements.txt](../telemetry-ingestion-service/requirements.txt):

- `pymysql`

Motivo:

- Solo se usa para conectar el worker provisional con la base legacy de MySQL.
- Si el puente desaparece, esa dependencia ya no aporta valor.

### 3. Las configuraciones MySQL en el servicio de ingesta

Eliminar de [telemetry-ingestion-service/app/config.py](../telemetry-ingestion-service/app/config.py):

- `MYSQL_URL`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `MYSQL_TABLE`
- `MYSQL_BATCH_SIZE`
- `MYSQL_POLL_INTERVAL_SECONDS`
- `MYSQL_CHECKPOINT_PATH`
- `MYSQL_NODE_ID_MAP`
- `MYSQL_TEMPERATURE_TYPE_ID`
- `MYSQL_HUMIDITY_TYPE_ID`
- `MYSQL_PH_TYPE_ID`
- La propiedad `mysql_connection_url`
- Las propiedades auxiliares relacionadas con batch, checkpoint y mapeo

Motivo:

- Esas variables y helpers solo existen para soportar la sincronización provisional desde MySQL.

### 4. El servicio nuevo en Docker Compose

Eliminar de [docker-compose.yml](../docker-compose.yml):

- El servicio `telemetry-mysql-sync-worker`
- El volumen `mysql-sync-state`

Motivo:

- El servicio `telemetry-mysql-sync-worker` es el proceso que ejecuta el puente provisional.
- El volumen `mysql-sync-state` solo guarda el checkpoint local para no reprocesar filas.

## Qué eliminar de la documentación

Eliminar o actualizar estas secciones:

- La sección `Worker provisional de sincronizacion MySQL -> broker` en [telemetry-ingestion-service/README.md](../telemetry-ingestion-service/README.md)
- Las variables `MYSQL_*` documentadas en ese README
- Cualquier nota que diga que el puente provisional debe usar Redis como broker compartido

Si el README principal del servicio o el README raíz mencionan este puente, también deben limpiarse para que no quede documentación obsoleta.

## Qué limpiar en `.env`

Eliminar del archivo [.env](../.env):

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `MYSQL_TABLE`
- `MYSQL_BATCH_SIZE`
- `MYSQL_POLL_INTERVAL_SECONDS`
- `MYSQL_CHECKPOINT_PATH`
- `MYSQL_NODE_ID_MAP` si fue agregado
- `MYSQL_TEMPERATURE_TYPE_ID` si fue agregado
- `MYSQL_HUMIDITY_TYPE_ID` si fue agregado
- `MYSQL_PH_TYPE_ID` si fue agregado

Motivo:

- Esas variables solo son necesarias para la capa temporal de lectura desde MySQL.

## Qué no borrar salvo que también retires el pipeline actual

No elimines estos elementos si el flujo normal del backend sigue usando broker y worker:

- [telemetry-ingestion-service/app/worker.py](../telemetry-ingestion-service/app/worker.py)
- [telemetry-ingestion-service/app/broker/](../telemetry-ingestion-service/app/broker/)
- La configuración `BROKER_*` en [telemetry-ingestion-service/app/config.py](../telemetry-ingestion-service/app/config.py)
- El servicio `telemetry-ingestion-worker` en [docker-compose.yml](../docker-compose.yml)

Motivo:

- Esos componentes pertenecen al flujo normal de ingesta del backend y no al puente temporal con MySQL.

## Orden recomendado de retiro

1. Confirmar que ya no entran datos nuevos desde MySQL legacy.
2. Confirmar que no quedan lotes pendientes en el worker nuevo.
3. Confirmar en PostgreSQL y en query-monitoring-service que las lecturas ya llegaron.
4. Parar el servicio `telemetry-mysql-sync-worker`.
5. Borrar el checkpoint si ya no habrá reanudación.
6. Eliminar el servicio de Compose y el volumen asociado.
7. Eliminar variables `MYSQL_*` de `.env`.
8. Eliminar `pymysql` del archivo de dependencias.
9. Borrar el archivo `mysql_worker.py`.
10. Limpiar la documentación restante.

## Validación después del retiro

Después de quitar el puente, valida lo siguiente:

- `docker compose ps` no debe mostrar `telemetry-mysql-sync-worker`.
- `docker compose logs telemetry-ingestion-worker` debe seguir mostrando consumo normal del broker si el flujo actual sigue activo.
- `docker compose logs query-monitoring-service` y los endpoints históricos deben seguir respondiendo con lecturas ya persistidas.
- No deben aparecer intentos de conexión a MySQL en logs de la aplicación.

## Si más adelante también se retira el broker

Este documento solo cubre el retiro del puente MySQL.

Si en algún momento decides eliminar también el broker, entonces tendrás que revisar además:

- `telemetry-ingestion-worker`
- `BROKER_*` en `.env`
- `app/broker/` y su configuración asociada
- Las referencias a Redis en `docker-compose.yml`

Eso es otro retiro distinto y no debe mezclarse con la eliminación del puente MySQL.
