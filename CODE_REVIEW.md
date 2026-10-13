# nginx/Shibboleth review and integration

Reviewed on 2026-10-12 against shared baseline
`dataquest-dev/docker-nginx-shib-auth@3d147b5e53750937c1e53a69470cf44845e7b208`
and the consuming project's Compose, nginx configuration and SP build/startup.
Updated on 2026-10-13 for Tomas's review and release-based consumption.

## Final scope

Docker is required for compilation. The existing `Dockerfile.shib` now separates
nginx compilation from its legacy standalone SP build. The `nginx-artifacts` target
outputs a reusable binary, upstream FastCGI includes and redistribution licenses.
Source versions and checksums remain Dockerfile build arguments, read by the existing
menu. No native build script or separate version file is added. Existing runtime
examples, launchers and deployment tools are preserved.

The consumer downloads the precompiled `ubuntu-22.04-amd64-nginx-1.30.5-r1` release
in its inline Docker build. Compose pins asset ID `638077019` and the archive's
SHA-256 digest. A temporary BuildKit secret authenticates to the private repository.
The source submodule pins the release commit `5974ce8` for inspection; it is not
part of the consumer build. The runtime uses the official nginx image, retains
its entrypoint and bakes this project's configuration.
The consumer's existing Shibboleth SP stays separate and uses TCP FastCGI.
There is no separate parent nginx Dockerfile and no automated registry publishing.
The shared CI compiles nginx with the three static modules using Docker, then retains
a compressed binary artifact and checksum for 30 days. Manual release requests
also publish that bundle as GitHub Release assets. The bundle excludes SP.
There is no image publishing or deployment.

## Findings resolved

| Priority | Finding | Final resolution |
|---|---|---|
| P1 | Original shared image starts its own SP with Unix sockets, while this project already owns a separate TCP SP. | Consumer installs the nginx-only binary release and retains its own SP. The default shared standalone build remains available to existing launchers. |
| P1 | Consumer needs template interpolation and the `main` log format. | Keep the official nginx image's entrypoint and base configuration in the consumer; bake project snippets/templates there. |
| P1 | Consumer discovery JSONP uses echo; former dynamic module loaders cannot load statically linked modules. | Compile echo 0.63, headers-more 0.40 and nginx-http-shibboleth 2.0.2 in; remove the old nginx Dockerfile/module loader. |
| P1 | Consumer's SP 3.5.2 download from a mutable `latest` path returns 404 and build errors were ignored. | Compile SP 3.6.0 from pinned HTTPS source URLs with SHA-256 verification and explicit dependencies. |
| P2 | Mainline nginx did not match the latest stable requirement clarified in review. | Pin nginx 1.30.5, confirmed latest stable at nginx.org on 2026-10-13. |
| P1 | Standalone nginx could not create temporary directories under the missing /var/cache/nginx parent. | Create that directory in the nginx build output; CI builds the standalone image and runs nginx -t. |
| P2 | nginx upgrades invalidated the standalone SP compilation cache. | Compile nginx and SP in independent stages and combine their outputs only in the final image. |
| P2 | Replacing the official nginx binary reduces the module set. | Document enabled modules and omitted optional modules/compiler hardening in both READMEs; extension configurations must use the compiled set. |
| P2 | Consumer suppresses key-generation errors and can start with incomplete persisted SP key pairs. | Reuse complete pairs, generate wholly absent pairs, reject incomplete pairs and validate SP configuration before starting supervisor. |
| P2 | Default SP debug tracing logs complete SAML identity messages. | Default message/security logging to INFO. |
| P2 | Runtime image library compatibility is required for a reusable dynamically linked binary. | Compile on Ubuntu 22.04, document compatible Linux libraries and verify the resulting binary in the consumer's official nginx runtime. |

Build inputs exclude local SP identities, TLS material and overrides. Linux scripts
use LF. Existing production certificates, SP keys and overrides were unchanged.

## Validation

- Docker artifact target builds nginx 1.30.5 on Ubuntu 22.04, checking all four
  source archives. Only SSL and the three required
  third-party modules are explicitly enabled; unrelated nginx features were removed.
- Consumer image inherits `/docker-entrypoint.sh` from the official nginx image.
- Standalone image passes `nginx -t` and reports nginx 1.30.5 / SP 3.6.0;
  nginx licenses are under `/usr/share/doc/nginx-shib/licenses`, with no `/licenses` root.
- A standalone build overriding nginx's version and checksum reuses the SP
  compilation layer, verified as `CACHED` in Docker's build output.
- Separate-service integration uses the real Shibboleth FastCGI service, real
  Fluent Bit, temporary TLS/SP/IdP keys and locally signed SAML assertions. Checks
  cover metadata, standard template rendering, backend/frontend routing, logging,
  internal authorizer access, discovery JSONP, anonymous login redirects,
  AuthnRequest generation, tampered-signature rejection, session creation,
  attribute forwarding, spoofed-header removal, replay rejection, restart,
  SP key preservation and incomplete-key rejection.
- Startup ordering includes the internal syslog service; the test backend has a
  TCP health check and nginx waits for it before loading upstream host names.
- The integration test also runs without nginx configuration bind mounts to
  verify the consumer image's baked defaults. All 20 checks pass in each mode
  (40 integration checks total).
- The stable nginx build also passes 20 checks against an external Ubuntu 22.04
  SP 3.3.0 package fixture, including signed SAML sessions and baked configuration.

Integration commands are in README.md. Tests use isolated project/network/volume
names and random loopback ports, and clean up their generated resources.
The backend/frontend are HTTP fixtures; a production federation, real DSpace
authentication implementation and architectures other than linux/amd64 were not
exercised. Consumers outside this image must supply compatible Linux libraries,
runtime directories, nginx worker identity and their own configuration.

Sources: [nginx releases](https://nginx.org/en/download.html),
[Shibboleth SP releases](https://shibboleth.net/downloads/service-provider/),
[module configuration](https://github.com/nginx-shib/nginx-http-shibboleth/blob/master/CONFIG.rst).
