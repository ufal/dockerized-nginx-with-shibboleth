# Basics

- shibboleth with fcgi support
- nginx with shibboleth module
- default config connects the two

The nginx and Shibboleth SP Docker builds download precompiled Ubuntu 22.04 / amd64
binaries from the private `dataquest-dev/docker-nginx-shib-auth` release
[`ubuntu-22.04-amd64-nginx-1.30.5-r2`](https://github.com/dataquest-dev/docker-nginx-shib-auth/releases/tag/ubuntu-22.04-amd64-nginx-1.30.5-r2):
nginx 1.30.5 and Shibboleth SP 3.6.0 built with FastCGI (`shibd`, `shibauthorizer`,
`shibresponder`). Release asset IDs and SHA-256 digests are pinned in Compose (nginx)
and `shibboleth/Dockerfile` (SP). Docker verifies each archive before installing it.

Authenticate GitHub CLI with read access to that repository, and pass its token
as a Docker build secret. On Linux:

```sh
export GH_TOKEN="$(gh auth token)"
docker compose up --build
```

On PowerShell:

```powershell
$env:GH_TOKEN = gh auth token
docker compose up --build
```

The token is mounted only in the download build step. It is not a Docker build
argument or container environment variable. A fine-grained token needs read access
to that repository's contents. Credentials are required when building the image;
the resulting image contains the release files and this project's configuration.

Docker is required. This project packages the downloaded nginx 1.30.5 binary in the
official nginx 1.30.5 image, retaining its standard entrypoint and template handling.
The service targets `linux/amd64`; the release's Ubuntu 22.04 binary works with the
compatible libraries in that image. Project snippets/templates are baked into the
consumer image and can be overridden with bind mounts. No separate nginx Dockerfile
or nginx compiler service is needed. SP remains the separate `shibboleth` service at
ports 12344/12345. Its Ubuntu 22.04 image installs the released SP with Ubuntu's
runtime libraries instead of compiling it. The release installs SP under `/usr`,
`/etc/shibboleth` and `/var`; the image keeps SP configuration, logs, cache and runtime
files at their former `/opt/shibboleth-sp/{etc,var}` paths, with `/etc/shibboleth` and
`/var/{log,cache,run}/shibboleth` linking there. Overrides, absolute `/opt/shibboleth-sp`
paths in configuration and the logs volume therefore keep working.

The `nginx/image` Git submodule is retained for source inspection and pinned to the
release's source commit on `ubuntu-22.04-amd64`. It is not required to build nginx's
consumer image. Initialize it with `git submodule update --init --recursive` when
inspecting the compiler. For upgrades, publish an upstream release and update its
asset IDs/digests, the official nginx version and the submodule pin together after testing.
Compose 2.17 or newer with BuildKit is required for inline builds and build secrets.
There is no automatic image publishing or deployment workflow. Building creates local images;
registry uploads are a separate operator action.
Both built services use local image names and `pull_policy: build`, so normal startup
builds from the pinned release assets.

## additional configs for nginx
Nginx is installed from the pinned upstream release. Project snippets (`proxy_params`, `shibboleth_auth`,
`ssl_params`, `cors_headers`) are mounted read-only at their original `/etc/nginx` paths; templates
are rendered from `/etc/nginx/templates` to `/etc/nginx/conf.d`.
`NGINX_ENVSUBST_FILTER=^NGINX_` preserves nginx's own variables. Modules are compiled in, so
additional configuration must not attempt to load the former dynamic `.so` modules.
This binary enables nginx's default modules, SSL, Shibboleth, headers-more and echo.
It replaces the official image's broader binary: HTTP/2, HTTP/3, realip, auth_request,
gzip_static, stub_status, sub, stream, mail, threads and the official compiler
hardening flags are not enabled. Check `nginx -V` and `nginx -t` before adding
directives in `nginx/locations/`. Additionally:
 
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
export GH_TOKEN="$(gh auth token)"
docker compose build nginx shibboleth
docker tag local/dspace-nginx-shib:1.30.5 local/nginx-shib-review:latest
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
