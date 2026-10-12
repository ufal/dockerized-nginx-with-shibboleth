# nginx/Shibboleth review and integration

Reviewed on 2026-10-12 against shared baseline
`dataquest-dev/docker-nginx-shib-auth@3d147b5e53750937c1e53a69470cf44845e7b208`
and the consuming project's Compose, nginx configuration and SP build/startup.

## Final scope

The shared repository is a compiler. Its native Linux `scripts/build.sh` downloads
checksum-pinned nginx 1.31.6 and the Shibboleth, headers-more and echo modules,
compiles them together, and outputs a reusable binary, upstream FastCGI includes
and redistribution licenses. Existing Dockerfiles, runtime examples and deployment
tools are preserved; the consumer uses the native compiler rather than those tools.

The consumer invokes that same script from its pinned Git submodule. Compose's
inline build packages the binary on the same official nginx base used to compile
it, retains the official entrypoint and bakes this project's configuration.
The consumer's existing Shibboleth SP stays separate and uses TCP FastCGI.
There is no separate parent nginx Dockerfile and no automated registry publishing.
No new shared runtime entrypoint, CI or deployment tooling is introduced.

## Findings resolved

| Priority | Finding | Final resolution |
|---|---|---|
| P1 | Original shared image starts its own SP with Unix sockets, while this project already owns a separate TCP SP. | Consumer uses the new native compiler's artifacts. Existing shared container tools are unchanged and are not used by this integration. |
| P1 | Consumer needs template interpolation and the `main` log format. | Keep the official nginx image's entrypoint and base configuration in the consumer; bake project snippets/templates there. |
| P1 | Consumer discovery JSONP uses echo; former dynamic module loaders cannot load statically linked modules. | Compile echo 0.63, headers-more 0.40 and nginx-http-shibboleth 2.0.2 in; remove the old nginx Dockerfile/module loader. |
| P1 | Consumer's SP 3.5.2 download from a mutable `latest` path returns 404 and build errors were ignored. | Compile SP 3.6.0 from pinned HTTPS source URLs with SHA-256 verification and explicit dependencies. |
| P2 | Default nginx version was stable rather than the newest requested release. | Pin nginx 1.31.6, confirmed latest mainline at nginx.org on the review date. |
| P2 | Consumer suppresses key-generation errors and can start with incomplete persisted SP key pairs. | Reuse complete pairs, generate wholly absent pairs, reject incomplete pairs and validate SP configuration before starting supervisor. |
| P2 | Default SP debug tracing logs complete SAML identity messages. | Default message/security logging to INFO. |
| P2 | Runtime image library compatibility is required for a reusable dynamically linked binary. | Compile inside the consumer's target base and document the artifact's architecture/ABI. |

Build inputs exclude local SP identities, TLS material and overrides. Linux scripts
use LF. Existing production certificates, SP keys and overrides were unchanged.

## Validation

- Compiler script builds nginx 1.31.6 on the official nginx image's Debian
  toolchain, checking all four source archives. Only SSL and the three required
  third-party modules are explicitly enabled; unrelated nginx features were removed.
- Consumer image inherits `/docker-entrypoint.sh` from the official nginx image.
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

Integration commands are in README.md. Tests use isolated project/network/volume
names and random loopback ports, and clean up their generated resources.
The backend/frontend are HTTP fixtures; a production federation, real DSpace
authentication implementation and architectures other than linux/amd64 were not
exercised. Consumers outside this image must supply compatible Linux libraries,
runtime directories, nginx worker identity and their own configuration.

Sources: [nginx releases](https://nginx.org/en/download.html),
[Shibboleth SP releases](https://shibboleth.net/downloads/service-provider/),
[module configuration](https://github.com/nginx-shib/nginx-http-shibboleth/blob/master/CONFIG.rst).
