# nginx/Shibboleth review and integration

Reviewed on 2026-10-12. Shared-repository baseline:
`dataquest-dev/docker-nginx-shib-auth@3d147b5e53750937c1e53a69470cf44845e7b208`.

The original shared image was not a direct replacement for this project's nginx image. The revised
`Dockerfile.shib --target nginx` is compatible with this project's separate FastCGI SP. Both the
standalone image and the separate-service integration have been built and exercised locally on
Docker Desktop, Linux amd64. nginx is pinned to 1.31.6 and the SP to 3.6.0.

The consumer gitlink pins the published shared revision
`5329410df53d381f27725892a41d3b3af7338ae2`; the upstream fixes are available in
[draft PR #1](https://github.com/dataquest-dev/docker-nginx-shib-auth/pull/1).

## Scope

Read all twelve original shared-repository files: both Dockerfiles, `nginx-shib.conf`,
`shib-entrypoint.sh`, the complete `tools/startme.py`, both batch launchers, `requirements.txt`,
`.dockerignore`, `.gitignore`, `.gitattributes` and `README.md`.
Reviewed the consuming Compose configuration, workflow, nginx templates/snippets, SP build script,
entrypoint, supervisor configuration, attribute map, SP templates, logging and Fluent Bit config.
Checked source downloads/checksums, module compilation, runtime paths, process handling, SP identity,
attribute trust boundaries and private-submodule checkout.

## Findings and resolutions

| Priority | Original finding | Resolution |
|---|---|---|
| P1 | `Dockerfile.shib` starts a bundled SP and uses Unix sockets. This project expects an nginx-only container calling its existing SP over TCP. | Added independent nginx/SP build stages and a `nginx` runtime target; Compose builds that target. |
| P1 | The shared image has no environment-template entrypoint, while the consumer depends on `${NGINX_*}` interpolation and its `main` access-log format. | Added filtered template rendering and a matching base nginx configuration. Mounted project snippets at their original paths. |
| P1 | The shared nginx omits echo, but discovery JSONP uses `echo_before_body`/`echo_after_body`. The consumer's old module loader also refers to dynamic `.so` files absent from the shared static build. | Compiled echo 0.63 alongside headers-more 0.40 and nginx-http-shibboleth 2.0.2; removed the consumer's obsolete Dockerfile/module loader. |
| P1 | The standalone example's `/secure/` invokes the authorizer but its shipped SP configuration has no RequestMap requiring authentication. A Shibboleth location alone does not require a session. | The image now ships a RequestMap with `authType="shibboleth"` and `requireSession="true"` for `/secure`. Custom configurations still need explicit mappings. |
| P1 | The consumer downloads SP 3.5.2 from `/latest/`; that URL returns 404. The original local build failed after the download error was ignored. | Updated to SP 3.6.0, immutable HTTPS paths, pinned SHA-256 checksums and immediate download-error handling. Added the explicit zlib build dependency. |
| P2 | Defaults use nginx 1.30.5 stable, rather than the requested newest release. | Both shared Dockerfiles now default to nginx 1.31.6 with its verified checksum. |
| P2 | Shared `nginx-shib.conf` uses a bundled header-clearing snippet that enumerates selected Shib headers and omits exported-assertion headers. | Clear `Auth-Type`, all `Shib-*`, `Remote-User` and every enabled default attribute ID. Consumer attribute clearing was also verified against its actual attribute map. |
| P2 | The standalone entrypoint ignores directory-setup failures and starts daemons without checking configuration. | Fail immediately on setup/configuration errors, validate as the SP user, clean FastCGI sockets, and preserve coordinated shutdown/failure status. |
| P2 | The configuration initializer can delete an existing SP directory and regenerate its identity. Its fixed temporary-container name can also collide with an unrelated container. | Refuse to replace an existing directory, remove forced key generation, and use a Docker-generated temporary container ID. |
| P2 | Consumer startup suppresses every key-generation error with `|| true`, including incomplete persisted key pairs. | Reuse complete pairs; generate only wholly absent pairs; reject incomplete pairs and validate the SP configuration before supervisor starts. |
| P2 | Consumer Shibboleth DEBUG logging records complete SAML messages, including the test assertion's identity attributes. | Default message/security tracing to INFO. Overrides remain available for deliberate troubleshooting. |
| P2 | The old CI Git build context cannot build the new private submodule or fetch it with the parent repository's token. | Explicitly check out the pinned gitlink SHA with a private-repository read credential, use filesystem build contexts, and publish only after integration tests pass. |

Additional portability changes: enforce LF for Linux scripts/templates, explicitly set entrypoint
execute permissions, exclude local SP overrides/keys from the image build context, and use separate
CI cache scopes. Existing local TLS certificates, SP keys and overrides were not changed.

## Validation

The following checks passed against the final local images:

- Plain nginx image builds; `nginx -t` succeeds and `nginx -v` reports 1.31.6.
- Standalone image builds; real shibd and the Unix-socket responder serve metadata; anonymous
  `/secure/` is denied; graceful restart and SIGKILL recovery work; keys survive; Docker stop exits
  zero; loss of nginx stops the container with a failure code.
- The configuration-tool regression test proves that an existing SP directory runs no Docker
  commands and its signing key remains byte-for-byte unchanged.
- The separate-service test uses the actual project nginx configuration, real FastCGI authorizer
  and responder, generated IdP metadata, and a cryptographically signed SAML assertion. It verifies
  metadata, backend/frontend routing, internal authorizer access, discovery JSONP, anonymous login
  redirects, AuthnRequest generation, signature-tampering rejection, session creation, verified
  attribute forwarding, spoofed-header removal, replay rejection, key preservation and incomplete-key
  rejection.
- Fluent Bit receives nginx's UDP syslog and writes the shared logs volume.
- Shell/Python syntax, YAML parsing and Git whitespace checks pass.

Tests use temporary keys/configuration, isolated container/network/volume names and random loopback
ports. Commands are documented in the project and submodule READMEs.

## Remaining deployment requirements and limits

The parent repository currently has no `NGINX_SUBMODULE_TOKEN` Actions secret. Supply a fine-grained
PAT or GitHub App token with Contents: read access to the private shared repository before running
parent CI. Fork PRs cannot access this private source with ordinary fork credentials.

The backend/frontend in the integration test are HTTP fixtures. A real production IdP, federation
registration, DSpace's own authentication implementation, remote deployment targets, interactive
terminal navigation and non-amd64 architectures were not exercised. Existing deployment-specific
metadata, public host names and TLS certificates still govern those environments. The standalone
default needs configured IdP metadata for login; without it protected requests fail closed.

Release references: [nginx downloads](https://nginx.org/en/download.html),
[Shibboleth SP releases](https://shibboleth.net/downloads/service-provider/),
[nginx Shibboleth configuration](https://github.com/nginx-shib/nginx-http-shibboleth/blob/master/CONFIG.rst).
