FROM nginx:stable as build

RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

ARG NGINX_RELEASE_ASSET_ID=638077019
ARG NGINX_RELEASE_SHA256=ce86499c6587fe5048f0fe5b85f69c009d2d941da3a2b47044ca12d2841dddc4
RUN --mount=type=secret,id=github_token,required=true \
    curl -fsSL -o /tmp/nginx.tar.gz \
      -H "Authorization: Bearer $(cat /run/secrets/github_token)" \
      -H "Accept: application/octet-stream" \
      "https://api.github.com/repos/dataquest-dev/docker-nginx-shib-auth/releases/assets/$NGINX_RELEASE_ASSET_ID" \
    && echo "$NGINX_RELEASE_SHA256  /tmp/nginx.tar.gz" | sha256sum -c - \
    && mkdir /tmp/build && tar -xzf /tmp/nginx.tar.gz -C /tmp/build

FROM nginx:1.30.5
COPY --from=build --chown=0:0 /tmp/build/usr/sbin/nginx /usr/sbin/nginx
COPY --from=build --chown=0:0 /tmp/build/etc/nginx/ /etc/nginx/
COPY --from=build --chown=0:0 /tmp/build/licenses/ /usr/share/doc/nginx-shib/licenses/
COPY conf/. /etc/nginx/

