# Colección de Postman

- Importa `vermicomposting.postman_collection.json`.
- Usa el gateway HTTPS en `https://localhost:8443` mediante variables:
  - `gatewayProtocol`
  - `gatewayHost`
  - `gatewayPort`
- Mantén los IDs del payload tal como están para cubrir los datos de prueba.
- Para TLS local autofirmado, desactiva la verificación SSL en Postman o utiliza `.certs/localhost.crt`.
