from collections.abc import Sequence

from prometheus_client import Gauge

query_cama_info = Gauge(
	"query_cama_info",
	"Camas registradas disponibles para tableros de dominio",
	["cama_id", "cama_nombre", "ubicacion"],
)

query_sensor_temperatura_celsius = Gauge(
	"query_sensor_temperatura_celsius",
	"Temperatura promedio por cama (ultima lectura por nodo)",
	["cama_id", "cama_nombre"],
)

query_sensor_humedad_relativa_percent = Gauge(
	"query_sensor_humedad_relativa_percent",
	"Humedad relativa promedio por cama (ultima lectura por nodo)",
	["cama_id", "cama_nombre"],
)

query_sensor_ph = Gauge(
	"query_sensor_ph",
	"pH promedio por cama (ultima lectura por nodo)",
	["cama_id", "cama_nombre"],
)

query_monitoring_total_camas = Gauge(
	"query_monitoring_total_camas",
	"Total de camas registradas",
)

query_monitoring_total_nodos = Gauge(
	"query_monitoring_total_nodos",
	"Total de nodos registrados",
)

query_monitoring_nodos_conectados = Gauge(
	"query_monitoring_nodos_conectados",
	"Nodos conectados segun ventana de monitoreo",
)

query_monitoring_nodos_desconectados = Gauge(
	"query_monitoring_nodos_desconectados",
	"Nodos desconectados segun ventana de monitoreo",
)

query_monitoring_lecturas_validas = Gauge(
	"query_monitoring_lecturas_validas",
	"Total de lecturas validas registradas",
)

query_monitoring_lecturas_invalidas = Gauge(
	"query_monitoring_lecturas_invalidas",
	"Total de lecturas invalidas registradas",
)

query_monitoring_nodo_conectado = Gauge(
	"query_monitoring_nodo_conectado",
	"Indica si un nodo esta conectado (1) o desconectado (0)",
	["nodo_id", "codigo_nodo", "cama_id", "cama_nombre"],
)


def update_cama_info_metrics(camas: Sequence) -> None:
	query_cama_info.clear()
	for cama in camas:
		query_cama_info.labels(
			cama_id=str(cama.cama_id),
			cama_nombre=str(cama.nombre),
			ubicacion=str(cama.ubicacion),
		).set(1)


def update_sensor_metrics_by_cama(rows: Sequence[dict]) -> None:
	query_sensor_temperatura_celsius.clear()
	query_sensor_humedad_relativa_percent.clear()
	query_sensor_ph.clear()

	for row in rows:
		labels = {
			"cama_id": str(row["cama_id"]),
			"cama_nombre": str(row["cama_nombre"]),
		}

		temperatura = row.get("temperatura")
		if temperatura is not None:
			query_sensor_temperatura_celsius.labels(**labels).set(float(temperatura))

		humedad = row.get("humedad")
		if humedad is not None:
			query_sensor_humedad_relativa_percent.labels(**labels).set(float(humedad))

		ph = row.get("ph")
		if ph is not None:
			query_sensor_ph.labels(**labels).set(float(ph))


query_monitoring_errores_por_nodo_total = Gauge(
	"query_monitoring_errores_por_nodo_total",
	"Total de errores por nodo sensor",
	["nodo_id", "codigo_nodo", "cama_id", "cama_nombre"],
)


query_monitoring_invalidaciones_por_causa_total = Gauge(
	"query_monitoring_invalidaciones_por_causa_total",
	"Total de invalidaciones por tipo de error",
	["tipo_error"],
)


def update_invalidaciones_por_causa_metrics(rows: Sequence[dict]) -> None:
	query_monitoring_invalidaciones_por_causa_total.clear()
	for row in rows:
		tipo_error = row.get("tipo_error", "desconocido")
		query_monitoring_invalidaciones_por_causa_total.labels(
			tipo_error=str(tipo_error),
		).set(float(row.get("total", 0)))


def update_errores_por_nodo_metrics(rows: Sequence[dict]) -> None:
	query_monitoring_errores_por_nodo_total.clear()
	for row in rows:
		nodo_id = row.get("nodo_id")
		if nodo_id is None:
			continue
		query_monitoring_errores_por_nodo_total.labels(
			nodo_id=str(nodo_id),
			codigo_nodo=str(row.get("codigo_nodo") or ""),
			cama_id=str(row.get("cama_id") or ""),
			cama_nombre=str(row.get("cama_nombre") or ""),
		).set(float(row.get("total_errores", 0)))


def update_nodo_connection_metrics(nodos: Sequence[dict]) -> None:
	query_monitoring_nodo_conectado.clear()
	for nodo in nodos:
		query_monitoring_nodo_conectado.labels(
			nodo_id=str(nodo["nodo_id"]),
			codigo_nodo=str(nodo["codigo_nodo"]),
			cama_id=str(nodo["cama_id"]),
			cama_nombre=str(nodo["cama_nombre"]),
		).set(1.0 if nodo["conectado"] else 0.0)


def update_monitoring_summary_metrics(summary: dict) -> None:
	query_monitoring_total_camas.set(float(summary.get("total_camas", 0)))
	query_monitoring_total_nodos.set(float(summary.get("total_nodos", 0)))
	query_monitoring_nodos_conectados.set(float(summary.get("nodos_conectados", 0)))
	query_monitoring_nodos_desconectados.set(float(summary.get("nodos_desconectados", 0)))
	query_monitoring_lecturas_validas.set(float(summary.get("lecturas_validas", 0)))
	query_monitoring_lecturas_invalidas.set(float(summary.get("lecturas_invalidas", 0)))
