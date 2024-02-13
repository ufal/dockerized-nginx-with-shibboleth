# Basics

- shibboleth with fcgi support
- nginx with shibboleth module
- default config connects the two

```
docker compose up
```

## additional configs for nginx
Nginx is built on top of official docker image; everyting in there should work. Additionally:
 
- default.conf has a `include /etc/nginx/locations/*;` and docker-compose has a bind mount for that dir. This can be used to configure addtional locations
- it's expected that `/ssl` bind mounted by docker compose from `./nginx/ssl` contains the following files:
  - `dhparam.pem` (generate with `openssl dhparam -out dhparam.pem 4096`)
  - `serverkey.pem`
  - `nginx_chain_cert.pem`

At the moment the locations provided by default should work with dspacev7, hence the
```
NGINX_TOMCAT
NGINX_NODE
```
in an `.env` file should be configured properly

as well as 
```
NGINX_SERVER_NAMES
NGINX_RESOLVERS
```
i.e. what you put in `nginx.conf` server context after `server_name`. Example:
```
NGINX_SERVER_NAMES="dspace-dev.example.org dspace-dev localhost"
```
or after `resolver`. Example

```
NGINX_RESOLVERS="1.1.1.1 8.8.8.8"
```

you can also connect to a different shibboleth fcgi by modifying:

```
NGINX_SHIBAUTHORIZER=
NGINX_SHIBRESPONDER=
```

The dspace backend location has a configurable `client_max_body_size` via
```
NGINX_MAX_BODY_SIZE
```

Nginx by default logs to stdout/stderr and syslog (provided by fluent-bit image). The syslog entries are written into the `logs` volume.

## additional configs for shibboleth

The shibboleth image (its entrypoint) has some similar mechanisms to what nginx does.

0. New signing and encrypt keys are generated if they were not provided in `/sp-keys` (bind mounted from `./shibboleth/sp-keys`)
1. `/overrides` (bind mounted by docker-compose from `./shibboleth/overrides`) gets overlaid on top of `/opt/shibboleth-sp` (this provides the option of overriding any defaults, e.g. `attribute-map.xml`)
2. `*.template` files from `/opt/shibboleth-sp/templates` get interpolated and the resulting files ends up in `/opt/shibboleth-sp/etc/shibboleth/${template%.template}`
3. `shibboleth2.xml` is run through an xinclude processor (to add custom MetadataProviders)

Shibboleth (shibd, authorizer and responder) are run via supervisord. Supervisors logs go to stdout/stderr. Shibd logs end up in logs volume.

You must set `SHIB_HOSTNAME` (in an .env file or some other way). By default this is used in the entityId and in the RequestMapper.

Example of the overrides dir:
```
shibboleth/overrides/
├── etc
│   └── shibboleth
│       ├── metadata-providers.xml
│       └── metadata2021.eduid.cz.crt.pem
├── templates
│   └── request-mapper.xml.template
└── var
    └── cache
        └── shibboleth
            └── proxied-idp.xml

6 directories, 4 files
```

where:
```
$cat shibboleth/overrides/etc/shibboleth/metadata-providers.xml
<MetadataProviders>
        <MetadataProvider xmlns="urn:mace:shibboleth:3.0:native:sp:config" type="XML" path="/opt/shibboleth-sp/var/cache/shibboleth/proxied-idp.xml"/>
        <!-- Federation metadata -->
        <!-- eduid -->
        <MetadataProvider xmlns="urn:mace:shibboleth:3.0:native:sp:config" type="XML" url="https://metadata.eduid.cz/entities/eduid+idp"
            backingFilePath="/opt/shibboleth-sp/var/run/shibboleth/eduid-idp.xml" reloadInterval="7200" legacyOrgNames="true" tagsInFeed="true">
            <MetadataFilter type="Signature" certificate="metadata2021.eduid.cz.crt.pem" verifyBackup="false"/>
                <MetadataFilter type="Include">
                    <Include>https://cas.cuni.cz/idp/shibboleth</Include>
                </MetadataFilter>
        </MetadataProvider>
</MetadataProviders>
```
configures 2 metadata sources

# Case study - local testing

1. create .env
```
SHIB_HOSTNAME=jm
NGINX_TOMCAT=dev-5.pc:85
NGINX_NODE=dev-5.pc:85
NGINX_SERVER_NAMES="jm localhost"
NGINX_RESOLVERS="1.1.1.1 8.8.8.8"
NGINX_MAX_BODY_SIZE=10G
```
2. in ./nginx/ssl
   ```
   openssl dhparam -out dhparam.pem 4096
   openssl genrsa -out /out/serverkey.pem 2048
   openssl req -new -x509 -key /out/serverkey.pem -out /out/servercert.pem -days 365
   cp server.crt nginx_chain_cert.pem
   ```
   (on win, you can use `docker run -it --rm  -v %cd%:/out nginx /bin/bash -c "CMD"`)
3. docker compose up


