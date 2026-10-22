FROM debian:trixie-slim

COPY shibboleth_sp_with_fastcgi.sh /shibboleth_sp_with_fastcgi.sh

RUN <<EOF
apt-get update
apt-get install -y wget build-essential libfcgi-dev libboost-all-dev openssl libssl-dev pkg-config libcurl4-openssl-dev
bash ./shibboleth_sp_with_fastcgi.sh
EOF

FROM debian:trixie-slim
RUN <<EOF
apt-get update
apt-get install -y  libfcgi0t64 openssl libssl3t64 libcurl4t64 libicu76 supervisor gettext-base libxml2-utils
rm -rf /var/lib/apt/lists/*
EOF
COPY --from=0 /opt/shibboleth-sp /opt/shibboleth-sp
COPY conf/* /opt/shibboleth-sp/etc/shibboleth/
COPY templates /opt/shibboleth-sp/templates
COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY shibd_fcgi.conf /etc/supervisor/conf.d/shibd_fcgi.conf

COPY docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT [ "/docker-entrypoint.sh" ]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

EXPOSE 12345
EXPOSE 12344