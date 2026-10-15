FROM debian:bookworm-slim

ARG SP_RELEASE=ubuntu-22.04-amd64-nginx-1.30.5-r2
ARG SP_ASSET=shibboleth-sp-3.6.0-fastcgi-ubuntu-22.04-amd64.tar.gz
ARG SP_RELEASE_SHA256=63c20a76198a77a3b75df296f5377b31424063db840ffc63965d2886ffcde27b
RUN --mount=type=secret,id=github_token,required=true <<'EOF'
set -e
apt-get update
apt-get install -y ca-certificates curl jq
api=https://api.github.com/repos/dataquest-dev/docker-nginx-shib-auth
auth="Authorization: Bearer $(cat /run/secrets/github_token)"
url=$(curl -fsSL -H "$auth" "$api/releases/tags/$SP_RELEASE" \
  | jq -er --arg name "$SP_ASSET" '.assets[] | select(.name == $name) | .url')
curl -fsSL -o /tmp/sp.tar.gz -H "$auth" -H "Accept: application/octet-stream" "$url"
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
