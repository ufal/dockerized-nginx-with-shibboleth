FROM ubuntu:22.04 AS sp-release
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl
# Pinned upstream release asset: Shibboleth SP 3.6.0 built --with-fastcgi for Ubuntu 22.04 / amd64.
ARG SP_RELEASE_ASSET_ID=640181282
ARG SP_RELEASE_SHA256=63c20a76198a77a3b75df296f5377b31424063db840ffc63965d2886ffcde27b
RUN --mount=type=secret,id=github_token,required=true \
    curl -fsSL --retry 3 \
      -H "Authorization: Bearer $(cat /run/secrets/github_token)" \
      -H "Accept: application/octet-stream" \
      -o /tmp/sp.tar.gz \
      "https://api.github.com/repos/dataquest-dev/docker-nginx-shib-auth/releases/assets/$SP_RELEASE_ASSET_ID" \
 && printf '%s  %s\n' "$SP_RELEASE_SHA256" /tmp/sp.tar.gz | sha256sum -c - \
 && mkdir /out && tar -xzf /tmp/sp.tar.gz -C /out \
 && test -x /out/usr/sbin/shibd \
 && test -x /out/usr/lib/shibboleth/shibauthorizer \
 && test -x /out/usr/lib/shibboleth/shibresponder \
 && test ! -e /out/usr/sbin/nginx

FROM ubuntu:22.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libcurl4 libfcgi0ldbl liblog4shib2 libxerces-c3.2 libxml-security-c20 openssl \
    supervisor gettext-base libxml2-utils \
 && rm -rf /var/lib/apt/lists/*
COPY --from=sp-release /out/usr/ /usr/
COPY --from=sp-release /out/etc/ /etc/
COPY --from=sp-release /out/var/ /var/
COPY --from=sp-release /out/licenses/ /usr/share/doc/shibboleth-sp/licenses/
# The release uses /etc and /var; keep their SP directories under the former
# /opt/shibboleth-sp layout, which overrides, absolute paths in existing
# configurations and the logs volume use.
RUN ldconfig \
 && mkdir -p /opt/shibboleth-sp/etc /opt/shibboleth-sp/var/log /opt/shibboleth-sp/var/cache \
             /opt/shibboleth-sp/var/run/shibboleth \
 && for dir in etc/shibboleth var/log/shibboleth var/cache/shibboleth; do \
      mv "/$dir" "/opt/shibboleth-sp/$dir" && ln -s "/opt/shibboleth-sp/$dir" "/$dir" || exit 1; \
    done \
 && ln -s /opt/shibboleth-sp/var/run/shibboleth /run/shibboleth
COPY conf/* /opt/shibboleth-sp/etc/shibboleth/
COPY templates /opt/shibboleth-sp/templates
COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY shibd_fcgi.conf /etc/supervisor/conf.d/shibd_fcgi.conf

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT [ "/docker-entrypoint.sh" ]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

EXPOSE 12345
EXPOSE 12344
