FROM debian:bookworm-slim

COPY shibboleth_sp_with_fastcgi.sh /shibboleth_sp_with_fastcgi.sh

RUN <<EOF
apt-get update
apt-get install -y wget build-essential libfcgi-dev libboost-all-dev openssl libssl-dev pkg-config libcurl4-openssl-dev
bash ./shibboleth_sp_with_fastcgi.sh
EOF

FROM debian:bookworm-slim
RUN <<EOF
apt-get update
apt-get install -y  libfcgi openssl libssl3 libcurl4 libicu72 supervisor
rm -rf /var/lib/apt/lists/*
EOF
COPY --from=0 /opt/shibboleth-sp /opt/shibboleth-sp
COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY shibd_fcgi.conf /etc/supervisor/conf.d/shibd_fcgi.conf

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

EXPOSE 12345
EXPOSE 12344