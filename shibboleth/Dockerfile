FROM debian:bookworm-slim

ARG SP_RELEASE_ASSET_ID=640181282
ARG SP_RELEASE_SHA256=63c20a76198a77a3b75df296f5377b31424063db840ffc63965d2886ffcde27b
RUN --mount=type=secret,id=github_token,required=true <<EOF
apt-get update
apt-get install -y ca-certificates curl
curl -fsSL -o /tmp/sp.tar.gz \
  -H "Authorization: Bearer $(cat /run/secrets/github_token)" \
  -H "Accept: application/octet-stream" \
  "https://api.github.com/repos/dataquest-dev/docker-nginx-shib-auth/releases/assets/$SP_RELEASE_ASSET_ID"
echo "$SP_RELEASE_SHA256  /tmp/sp.tar.gz" | sha256sum -c -
mkdir /out && tar -xzf /tmp/sp.tar.gz -C /out
EOF

FROM ubuntu:22.04
RUN <<EOF
apt-get update
apt-get install -y  libfcgi openssl libssl3 libcurl4 liblog4shib2 libxerces-c3.2 libxml-security-c20 supervisor gettext-base libxml2-utils
rm -rf /var/lib/apt/lists/*
EOF
COPY --from=0 /out/usr/ /usr/
COPY --from=0 /out/etc/ /etc/
COPY --from=0 /out/var/ /var/
COPY --from=0 /out/licenses/ /usr/share/doc/shibboleth-sp/licenses/
RUN <<EOF
ldconfig
mkdir -p /opt/shibboleth-sp/etc /opt/shibboleth-sp/var/log /opt/shibboleth-sp/var/cache /opt/shibboleth-sp/var/run/shibboleth
for dir in etc/shibboleth var/log/shibboleth var/cache/shibboleth; do
  mv "/$dir" "/opt/shibboleth-sp/$dir" && ln -s "/opt/shibboleth-sp/$dir" "/$dir" || exit 1
done
ln -s /opt/shibboleth-sp/var/run/shibboleth /run/shibboleth
EOF
COPY conf/* /opt/shibboleth-sp/etc/shibboleth/
COPY templates /opt/shibboleth-sp/templates
COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY shibd_fcgi.conf /etc/supervisor/conf.d/shibd_fcgi.conf

COPY docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT [ "/docker-entrypoint.sh" ]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

EXPOSE 12345
EXPOSE 12344
