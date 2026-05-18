FROM alpine:3.20

RUN apk add --no-cache openssl

COPY provision-local-cert.sh /usr/local/bin/provision-local-cert.sh
RUN chmod +x /usr/local/bin/provision-local-cert.sh

ENTRYPOINT ["/usr/local/bin/provision-local-cert.sh"]
