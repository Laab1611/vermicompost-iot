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

query_monitoring_lecturas_invalidas = Gauge(
	"query_monitoring_lecturas_invalidas",
	"Total de lecturas invalidas registradas",
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


def update_monitoring_summary_metrics(summary: dict) -> None:
	query_monitoring_total_camas.set(float(summary.get("total_camas", 0)))
	query_monitoring_total_nodos.set(float(summary.get("total_nodos", 0)))
	query_monitoring_nodos_conectados.set(float(summary.get("nodos_conectados", 0)))
	query_monitoring_nodos_desconectados.set(float(summary.get("nodos_desconectados", 0)))
	query_monitoring_lecturas_invalidas.set(float(summary.get("lecturas_invalidas", 0)))
