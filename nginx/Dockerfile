FROM nginx:stable as build

RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

ARG NGINX_RELEASE=ubuntu-22.04-amd64-nginx-1.30.5-r1
ARG NGINX_ASSET=nginx-1.30.5-shibboleth-ubuntu-22.04-amd64.tar.gz
ARG NGINX_RELEASE_SHA256=ce86499c6587fe5048f0fe5b85f69c009d2d941da3a2b47044ca12d2841dddc4
RUN --mount=type=secret,id=github_token,required=true \
    api=https://api.github.com/repos/dataquest-dev/docker-nginx-shib-auth \
    && auth="Authorization: Bearer $(cat /run/secrets/github_token)" \
    && url=$(curl -fsSL -H "$auth" "$api/releases/tags/$NGINX_RELEASE" \
       | jq -er --arg name "$NGINX_ASSET" '.assets[] | select(.name == $name) | .url') \
    && curl -fsSL -o /tmp/nginx.tar.gz -H "$auth" -H "Accept: application/octet-stream" "$url" \
    && echo "$NGINX_RELEASE_SHA256  /tmp/nginx.tar.gz" | sha256sum -c - \
    && mkdir /tmp/build && tar -xzf /tmp/nginx.tar.gz -C /tmp/build

FROM nginx:1.30.5
COPY --from=build --chown=0:0 /tmp/build/usr/sbin/nginx /usr/sbin/nginx
COPY --from=build --chown=0:0 /tmp/build/etc/nginx/ /etc/nginx/
COPY --from=build --chown=0:0 /tmp/build/licenses/ /usr/share/doc/nginx-shib/licenses/
COPY conf/. /etc/nginx/

