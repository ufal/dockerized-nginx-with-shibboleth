FROM nginx:stable as build

RUN apt-get update && apt-get install -y \
    gcc \
    make \
    libpcre3-dev \
    zlib1g-dev \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/build

RUN wget -qO - https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz | tar -xzf - 
RUN wget -qO - https://github.com/nginx-shib/nginx-http-shibboleth/archive/v2.0.2.tar.gz | tar -xzf -
RUN wget -qO - https://github.com/openresty/headers-more-nginx-module/archive/v0.34.tar.gz | tar -xzf -
RUN wget -qO - https://github.com/openresty/echo-nginx-module/archive/v0.63.tar.gz | tar -xzf -

WORKDIR /tmp/build/nginx-${NGINX_VERSION}
RUN ./configure --with-compat --add-dynamic-module=../nginx-http-shibboleth-2.0.2 --add-dynamic-module=../headers-more-nginx-module-0.34 --add-dynamic-module=../echo-nginx-module-0.63 && make modules

FROM nginx:stable
COPY --from=build /tmp/build/nginx-${NGINX_VERSION}/objs/ngx_http_headers_more_filter_module.so /usr/lib/nginx/modules/
COPY --from=build /tmp/build/nginx-${NGINX_VERSION}/objs/ngx_http_shibboleth_module.so /usr/lib/nginx/modules/
COPY --from=build /tmp/build/nginx-${NGINX_VERSION}/objs/ngx_http_echo_module.so /usr/lib/nginx/modules/
COPY conf/. /etc/nginx/
RUN sed -i '1i\include /etc/nginx/modules-enabled/*.conf;' /etc/nginx/nginx.conf

