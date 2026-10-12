# Basics

- shibboleth with fcgi support
- nginx with shibboleth module
- default config connects the two

For a source build, nginx uses the private `dataquest-dev/docker-nginx-shib-auth` Git submodule at
`nginx/image`. You need read access to that repository. Initialize it before building:

```sh
git submodule update --init --recursive
docker compose up --build
```

Compose calls the submodule's native `scripts/build.sh` to compile nginx 1.31.6 with the
Shibboleth, headers-more and echo modules. That build supplies the binary, FastCGI includes
and licenses. The shared repository's pre-existing container/deployment tools are retained.
This project's inline Compose build packages the binary in the official nginx 1.31.6 image,
retaining its standard entrypoint and template handling. Compilation uses the same base as
the runtime to keep library ABIs compatible. Project snippets/templates are baked into this
consumer image and can be overridden with bind mounts. No separate nginx Dockerfile is needed.
The SP remains the separate `shibboleth` service at ports 12344/12345 and builds SP 3.6.0.
nginx versions/checksums are pinned in the submodule's `versions.env`; update its revision and
the official image version in Compose together after testing upgrades.
Compose 2.17 or newer with BuildKit is required for inline builds and additional contexts.
There is no automatic image publishing or deployment workflow. Building creates local images;
registry uploads are a separate operator action.
Both built services use local image names and `pull_policy: build`, so normal startup uses
the pinned sources instead of pulling an older registry tag.

## additional configs for nginx
Nginx is built from source in the shared submodule. Project snippets (`proxy_params`, `shibboleth_auth`,
`ssl_params`, `cors_headers`) are mounted read-only at their original `/etc/nginx` paths; templates
are rendered from `/etc/nginx/templates` to `/etc/nginx/conf.d`.
`NGINX_ENVSUBST_FILTER=^NGINX_` preserves nginx's own variables. Modules are compiled in, so
additional configuration must not attempt to load the former dynamic `.so` modules. Additionally:
 
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
1. `/overrides` (bind mounted by docker-compose from `./shibboleth/overrides`) gets overlaid on top of `/opt/shibboleth-sp` (this provides the option of overriding any defaults, e.g. `attribute-map.xml`. You can provide `shibboleth/overrides/etc/shibboleth/md_template.xml` and this will be used as a template attribute on the `MetadataGenerator` `Handler` (`/Shibboleth.sso/Metadata`))
2. `*.template` files from `/opt/shibboleth-sp/templates` get interpolated and the resulting files ends up in `/opt/shibboleth-sp/etc/shibboleth/${template%.template}`
3. `shibboleth2.xml` is run through an xinclude processor (to add custom MetadataProviders)

Shibboleth (shibd, authorizer and responder) are run via supervisord. Supervisors logs go to stdout/stderr. Shibd logs end up in logs volume.

You must set `SHIB_HOSTNAME` (in an .env file or some other way). By default this is used in the entityId and in the RequestMapper.
Keep the existing signing/encryption key pairs in `shibboleth/sp-keys`. Startup reuses complete
pairs and fails on an incomplete pair; it generates keys only when both files of a pair are absent.

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

see https://github.com/ufal/dockerized-nginx-with-shibboleth/wiki/casestudy

## Integration verification

```sh
docker compose build nginx shibboleth
docker tag local/dspace-nginx-shib:1.31.6 local/nginx-shib-review:latest
docker tag local/dspace-shibboleth:3.6.0 local/shibboleth-review:latest
docker pull python:3.11-slim
docker compose pull syslog
python -m pip install -r tests/requirements.txt
python tests/integration.py
python tests/integration.py --image-only
```

The test starts an isolated Compose project with temporary TLS/SP/IdP keys and random loopback
ports, and removes its containers and volumes afterwards. It uses this project's actual nginx
templates, Shibboleth FastCGI service and Fluent Bit collector, an HTTP fixture for the DSpace
backend/frontend, and a locally signed SAML assertion. It checks metadata, discovery JSONP,
redirects, attribute forwarding, logging, header spoofing, replay rejection and SP key preservation.
The second run verifies the baked image without nginx configuration bind mounts. It does not test a production federation
or DSpace's own authentication code. Review details and validation results are in `CODE_REVIEW.md`.
