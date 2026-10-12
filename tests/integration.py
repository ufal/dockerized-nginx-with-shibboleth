"""Docker integration test with real Shibboleth and a locally signed SAML response.

Uses temporary keys/configuration, an isolated Compose project and random local
ports. No production .env, overrides, keys, containers or volumes are changed.
Run after building local/nginx-shib-review and local/shibboleth-review.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit
import ssl

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
IDP = "https://idp.example.test/idp"
ENTITY = "https://localhost/shibboleth-sp"
ACS = "https://localhost/Shibboleth.sso/SAML2/POST"
BASE = "urn:oasis:names:tc:SAML:2.0"
SAML = BASE + ":assertion"
PROTO = BASE + ":protocol"
DS = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"


def run(*args, env=None):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"{args!r}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS {message}", flush=True)


def signed_response(directory):
    now = datetime.now(timezone.utc)
    stamp = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    response = ET.Element(f"{{{PROTO}}}Response", nsmap={"samlp": PROTO, "saml": SAML},
                          ID="_" + uuid.uuid4().hex, Version="2.0", IssueInstant=stamp(now),
                          Destination=ACS)
    ET.SubElement(response, f"{{{SAML}}}Issuer").text = IDP
    status = ET.SubElement(response, f"{{{PROTO}}}Status")
    ET.SubElement(status, f"{{{PROTO}}}StatusCode", Value=BASE + ":status:Success")
    assertion = ET.SubElement(response, f"{{{SAML}}}Assertion", ID="_" + uuid.uuid4().hex,
                              Version="2.0", IssueInstant=stamp(now))
    ET.SubElement(assertion, f"{{{SAML}}}Issuer").text = IDP
    subject = ET.SubElement(assertion, f"{{{SAML}}}Subject")
    ET.SubElement(subject, f"{{{SAML}}}NameID", Format=BASE + ":nameid-format:transient").text = "test-user"
    confirm = ET.SubElement(subject, f"{{{SAML}}}SubjectConfirmation", Method=BASE + ":cm:bearer")
    ET.SubElement(confirm, f"{{{SAML}}}SubjectConfirmationData", Recipient=ACS,
                  NotOnOrAfter=stamp(now + timedelta(minutes=5)))
    conditions = ET.SubElement(assertion, f"{{{SAML}}}Conditions",
                               NotBefore=stamp(now - timedelta(minutes=1)),
                               NotOnOrAfter=stamp(now + timedelta(minutes=5)))
    audience = ET.SubElement(conditions, f"{{{SAML}}}AudienceRestriction")
    ET.SubElement(audience, f"{{{SAML}}}Audience").text = ENTITY
    authn = ET.SubElement(assertion, f"{{{SAML}}}AuthnStatement", AuthnInstant=stamp(now),
                          SessionIndex="_" + uuid.uuid4().hex)
    context = ET.SubElement(authn, f"{{{SAML}}}AuthnContext")
    ET.SubElement(context, f"{{{SAML}}}AuthnContextClassRef").text = BASE + ":ac:classes:PasswordProtectedTransport"
    attrs = ET.SubElement(assertion, f"{{{SAML}}}AttributeStatement")
    for name, value in [("urn:oid:1.3.6.1.4.1.5923.1.1.1.6", "tester@example.test"),
                        ("urn:oid:0.9.2342.19200300.100.1.3", "tester@example.test")]:
        attr = ET.SubElement(attrs, f"{{{SAML}}}Attribute", Name=name,
                             NameFormat=BASE + ":attrname-format:uri")
        ET.SubElement(attr, f"{{{SAML}}}AttributeValue").text = value

    # Enveloped RSA-SHA256 signature over the assertion, exclusive canonicalization.
    digest = base64.b64encode(hashlib.sha256(ET.tostring(assertion, method="c14n", exclusive=True)).digest()).decode()
    signature = ET.Element(f"{{{DS}}}Signature", nsmap={"ds": DS})
    assertion.insert(1, signature)
    info = ET.SubElement(signature, f"{{{DS}}}SignedInfo")
    ET.SubElement(info, f"{{{DS}}}CanonicalizationMethod", Algorithm=C14N)
    ET.SubElement(info, f"{{{DS}}}SignatureMethod", Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256")
    ref = ET.SubElement(info, f"{{{DS}}}Reference", URI="#" + assertion.get("ID"))
    transforms = ET.SubElement(ref, f"{{{DS}}}Transforms")
    ET.SubElement(transforms, f"{{{DS}}}Transform", Algorithm=DS + "enveloped-signature")
    ET.SubElement(transforms, f"{{{DS}}}Transform", Algorithm=C14N)
    ET.SubElement(ref, f"{{{DS}}}DigestMethod", Algorithm="http://www.w3.org/2001/04/xmlenc#sha256")
    ET.SubElement(ref, f"{{{DS}}}DigestValue").text = digest
    key = serialization.load_pem_private_key((directory / "idp-key.pem").read_bytes(), password=None)
    value = key.sign(ET.tostring(info, method="c14n", exclusive=True), padding.PKCS1v15(), hashes.SHA256())
    ET.SubElement(signature, f"{{{DS}}}SignatureValue").text = base64.b64encode(value).decode()
    keyinfo = ET.SubElement(signature, f"{{{DS}}}KeyInfo")
    data = ET.SubElement(keyinfo, f"{{{DS}}}X509Data")
    ET.SubElement(data, f"{{{DS}}}X509Certificate").text = cert_text(directory / "idp-cert.pem")
    return base64.b64encode(ET.tostring(response)).decode()


def cert_text(path):
    return "".join(line for line in path.read_text().splitlines() if not line.startswith("---"))


def key_hashes(directory, image):
    # Keep root-owned SP private keys at mode 0600; read hashes inside Docker.
    output = run("docker", "run", "--rm", "--entrypoint", "bash", "-v", f"{directory}:/keys:ro",
                 image, "-c", "sha256sum /keys/*.pem")
    return {Path(path).name: digest for digest, path in (line.split() for line in output.splitlines())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nginx-image", default="local/nginx-shib-review:latest")
    parser.add_argument("--shib-image", default="local/shibboleth-review:latest")
    parser.add_argument("--image-only", action="store_true", help="verify baked nginx configuration without config bind mounts")
    args = parser.parse_args()
    project = "shib-review-" + uuid.uuid4().hex[:10]
    with tempfile.TemporaryDirectory(prefix="shib-review-") as tmp:
        directory = Path(tmp)
        for subdir in ["ssl", "keys", "overrides/etc/shibboleth", "overrides/templates", "locations"]:
            (directory / subdir).mkdir(parents=True)
        sp_template = (ROOT / "shibboleth/templates/shibboleth2.xml.template").read_text(encoding="utf-8")
        (directory / "overrides/templates/shibboleth2.xml.template").write_text(
            sp_template.replace('supportContact="root@localhost"', 'supportContact="${TEST_SUPPORT_CONTACT}"'),
            encoding="utf-8")
        # The fixture IdP key must be readable by the Python process that signs
        # assertions. Generate fixture TLS/IdP files as that host user on Linux.
        generator_user = ["--user", f"{os.getuid()}:{os.getgid()}"] if hasattr(os, "getuid") else []
        run("docker", "run", "--rm", *generator_user, "-v", f"{directory}:/test", args.nginx_image,
            "bash", "-ec", "openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=localhost "
            "-keyout /test/ssl/serverkey.pem -out /test/ssl/nginx_chain_cert.pem; "
            "openssl genpkey -genparam -algorithm DH -pkeyopt group:ffdhe2048 -out /test/ssl/dhparam.pem; "
            "openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=test-idp "
            "-keyout /test/idp-key.pem -out /test/idp-cert.pem")
        metadata = f'''<MetadataProviders>
          <MetadataProvider xmlns="urn:mace:shibboleth:3.0:native:sp:config" type="XML" path="idp.xml"/>
        </MetadataProviders>'''
        overrides = directory / "overrides/etc/shibboleth"
        (overrides / "metadata-providers.xml").write_text(metadata, encoding="utf-8")
        (overrides / "idp.xml").write_text(f'''<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{IDP}">
          <IDPSSODescriptor protocolSupportEnumeration="{PROTO}">
            <Extensions><Scope xmlns="urn:mace:shibboleth:metadata:1.0" regexp="false">example.test</Scope></Extensions>
            <KeyDescriptor use="signing"><KeyInfo xmlns="{DS}"><X509Data><X509Certificate>{cert_text(directory / 'idp-cert.pem')}</X509Certificate></X509Data></KeyInfo></KeyDescriptor>
            <SingleSignOnService Binding="{BASE}:bindings:HTTP-Redirect" Location="https://idp.example.test/sso"/>
          </IDPSSODescriptor>
        </EntityDescriptor>''', encoding="utf-8")
        env = dict(os.environ, SHIB_HOSTNAME="localhost", NGINX_TOMCAT="backend:8080",
                   NGINX_NODE="backend:8080", NGINX_SERVER_NAMES="localhost", NGINX_RESOLVERS="127.0.0.11",
                   NGINX_SHIBAUTHORIZER="shibboleth:12344", NGINX_SHIBRESPONDER="shibboleth:12345",
                   NGINX_MAX_BODY_SIZE="10G")
        env_file = directory / "empty.env"
        env_file.write_text("", encoding="utf-8")
        config = json.loads(run("docker", "compose", "--env-file", str(env_file), "-p", project, "-f", str(ROOT / "docker-compose.yml"),
                                "config", "--format", "json", env=env))
        check(all(resource.get("name", "").startswith(project + "_")
                  and not resource.get("external", False)
                  for kind in ("networks", "volumes") for resource in config.get(kind, {}).values()),
              "Compose networks and volumes use the random test project name")
        config.pop("name", None)
        nginx = config["services"]["nginx"]
        nginx.pop("build", None)
        nginx.pop("pull_policy", None)
        nginx["image"] = args.nginx_image
        nginx["restart"] = "no"
        nginx["ports"] = ["127.0.0.1::443", "127.0.0.1::80"]
        expected_config = {f"/etc/nginx/{name}": ROOT / "nginx/conf" / name
                           for name in ("proxy_params", "shibboleth_auth", "ssl_params", "cors_headers", "templates")}
        actual_config = {mount["target"]: mount for mount in nginx["volumes"]}
        check(all(target in actual_config and actual_config[target]["type"] == "bind"
                  and actual_config[target].get("read_only", False)
                  and Path(actual_config[target]["source"]).resolve() == source.resolve()
                  for target, source in expected_config.items()),
              "Compose mounts the actual project configuration at its original include paths")
        def replace_mount(service, target, source):
            mounts = [mount for mount in service["volumes"] if mount["target"] == target]
            if len(mounts) != 1 or mounts[0]["type"] != "bind":
                raise AssertionError(f"Expected one bind mount for {target}")
            mounts[0]["source"] = str(source)

        replace_mount(nginx, "/ssl", directory / "ssl")
        replace_mount(nginx, "/etc/nginx/locations", directory / "locations")
        if args.image_only:
            nginx["volumes"] = [mount for mount in nginx["volumes"]
                                if mount["target"] in ("/ssl", "/etc/nginx/locations")]
        shib = config["services"]["shibboleth"]
        shib.pop("build", None)
        shib.pop("pull_policy", None)
        shib["image"] = args.shib_image
        shib["restart"] = "no"
        shib["environment"]["TEST_SUPPORT_CONTACT"] = "support@example.test"
        replace_mount(shib, "/sp-keys", directory / "keys")
        replace_mount(shib, "/overrides", directory / "overrides")
        config["services"]["syslog"].pop("ports", None)
        config["services"]["syslog"]["restart"] = "no"
        config["services"]["backend"] = {"image": "python:3.11-slim", "command": ["python", "/backend.py"],
                                       "volumes": [f"{ROOT / 'tests/backend.py'}:/backend.py:ro"],
                                       "healthcheck": {
                                           "test": ["CMD", "python", "-c", "import socket; socket.create_connection(('127.0.0.1',8080),timeout=1).close()"],
                                           "interval": "1s", "timeout": "2s", "retries": 30}}
        nginx["depends_on"]["backend"] = {"condition": "service_healthy"}
        compose_file = directory / "compose.json"
        compose_file.write_text(json.dumps(config), encoding="utf-8")
        compose = ["docker", "compose", "-p", project, "-f", str(compose_file)]
        cookie = ""
        try:
            run(*compose, "up", "-d", "--no-build", "--pull", "never")
            if "nginx-compiler" in run(*compose, "ps", "--status", "running", "--services").splitlines():
                raise AssertionError("The compiler must remain a build dependency with zero containers")
            port = int(run(*compose, "port", "nginx", "443").rsplit(":", 1)[1])

            def request(path, method="GET", body=None, headers=None, use_cookie=True):
                connection = http.client.HTTPSConnection("127.0.0.1", port, timeout=10,
                                                         context=ssl._create_unverified_context())
                incoming = {"Host": "localhost"}
                if cookie and use_cookie:
                    incoming["Cookie"] = cookie
                incoming.update(headers or {})
                connection.request(method, path, body=body, headers=incoming)
                response = connection.getresponse()
                result = response.status, response.read(), dict(response.getheaders())
                connection.close()
                return result

            status = 0
            body = b""
            for _ in range(60):
                try:
                    status, body, _ = request("/Shibboleth.sso/Metadata")
                    if status == 200:
                        break
                except OSError:
                    pass
                time.sleep(1)
            check(status == 200 and ENTITY.encode() in body, "real SP metadata served over HTTPS")
            rendered_sp = run(*compose, "exec", "-T", "shibboleth", "cat", "/opt/shibboleth-sp/etc/shibboleth/shibboleth2.xml")
            check('supportContact="support@example.test"' in rendered_sp,
                  "existing SP templates interpolate custom environment variables")
            run(*compose, "exec", "-T", "nginx", "nginx", "-t")
            check("nginx/1.31.6" in run(*compose, "exec", "-T", "nginx", "bash", "-c", "nginx -v 2>&1"),
                  "latest mainline nginx 1.31.6 is running")
            check(json.loads(request("/server/api/core/items")[1])["path"] == "/server/api/core/items",
                  "DSpace backend path is preserved")
            check(json.loads(request("/ui-route")[1])["path"] == "/ui-route", "frontend proxy works")
            for _ in range(15):
                logged = run(*compose, "exec", "-T", "shibboleth", "bash", "-c",
                             "grep -l '/server/api/core/items' /opt/shibboleth-sp/var/log/nginx/* 2>/dev/null || true")
                if logged:
                    break
                time.sleep(1)
            check(bool(logged), "real Fluent Bit receives nginx syslog and writes the shared logs volume")
            check(request("/shibauthorizer")[0] == 404, "FastCGI authorizer is internal")
            status, body, _ = request("/Shibboleth.sso/DiscoFeed/jsonp")
            check(status == 200 and body.startswith(b"dj_md_1(") and body.rstrip().endswith(b");"),
                  "discovery JSONP echo filters work with real FastCGI responder")
            protected = "/server/api/authn/shibboleth"
            status, _, headers = request(protected, headers={"eppn": "attacker@example.test", "Remote-User": "attacker"})
            check(status == 302 and "/idpdiscovery/" in headers.get("Location", ""),
                  "anonymous/spoofed request requires authentication")
            status, _, headers = request("/Shibboleth.sso/Login?" + urlencode({"entityID": IDP, "target": "https://localhost" + protected}))
            check(status == 302 and headers.get("Location", "").startswith("https://idp.example.test/sso?"),
                  "real SP generates an AuthnRequest to the configured test IdP")
            saml = signed_response(directory)
            tampered = base64.b64encode(base64.b64decode(saml).replace(b"tester@example.test", b"forged@example.test")).decode()
            status, _, headers = request("/Shibboleth.sso/SAML2/POST", "POST",
                                         urlencode({"SAMLResponse": tampered}),
                                         {"Content-Type": "application/x-www-form-urlencoded"})
            check(status >= 400 and "_shibsession_" not in headers.get("Set-Cookie", ""),
                  "tampered signed assertion is rejected")
            # Shibboleth records message IDs before signature validation, even for rejected responses.
            saml = signed_response(directory)
            status, body, headers = request("/Shibboleth.sso/SAML2/POST", "POST",
                                            urlencode({"SAMLResponse": saml, "RelayState": "https://localhost" + protected}),
                                            {"Content-Type": "application/x-www-form-urlencoded"})
            check(status == 302 and "_shibsession_" in headers.get("Set-Cookie", ""),
                  f"signed SAML assertion creates a session (status {status})")
            cookie = headers["Set-Cookie"].split(";", 1)[0]
            status, body, _ = request(protected, headers={"eppn": "attacker@example.test", "mail": "attacker@example.test",
                                                         "givenName": "attacker", "Auth-Type": "attacker",
                                                         "Remote-User": "attacker", "Shib-Identity-Provider": "attacker"})
            upstream = {k.lower(): v for k, v in json.loads(body)["headers"].items()}
            check(status == 200 and upstream.get("eppn") == "tester@example.test" and upstream.get("mail") == "tester@example.test",
                  "authenticated attributes reach the backend")
            check("attacker" not in json.dumps(upstream) and "givenname" not in upstream,
                  "spoofed attributes and Shibboleth headers are removed")
            status, body, _ = request("/Shibboleth.sso/SAML2/POST", "POST", urlencode({"SAMLResponse": saml}),
                                     {"Content-Type": "application/x-www-form-urlencoded"}, use_cookie=False)
            check(status >= 400, "replayed assertion is rejected")
            keys_before = key_hashes(directory / "keys", args.shib_image)
            run(*compose, "restart", "shibboleth")
            recovered = False
            for _ in range(30):
                time.sleep(1)
                if request("/Shibboleth.sso/Metadata")[0] == 200:
                    recovered = True
                    break
            check(recovered, "Shibboleth serves metadata again after restart")
            keys_after = key_hashes(directory / "keys", args.shib_image)
            check(keys_before == keys_after and len(keys_after) == 4, "SP signing/encryption keys survive restart")
            partial = directory / "partial-keys"
            partial.mkdir()
            run("docker", "run", "--rm", "--entrypoint", "bash", "-v", f"{directory / 'keys'}:/keys:ro",
                "-v", f"{partial}:/partial", args.shib_image, "-c", "cp /keys/sp-signing-key.pem /partial/")
            partial_before = key_hashes(partial, args.shib_image)
            failed = subprocess.run(["docker", "run", "--rm", "-e", "SHIB_HOSTNAME=localhost",
                                     "-v", f"{partial}:/sp-keys", args.shib_image],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace")
            check(failed.returncode != 0 and "Incomplete SP signing key pair" in failed.stderr
                  and key_hashes(partial, args.shib_image) == partial_before
                  and not (partial / "sp-signing-cert.pem").exists(),
                  "incomplete existing key pair fails without replacing the SP identity")
        except Exception:
            logs = subprocess.run([*compose, "logs", "--tail", "80"], capture_output=True,
                                  text=True, encoding="utf-8", errors="replace")
            print(logs.stdout + logs.stderr, flush=True)
            diagnostic = subprocess.run([*compose, "exec", "-T", "shibboleth", "bash", "-c",
                                         "tail -80 /opt/shibboleth-sp/var/log/shibboleth/shibd.log || true"],
                                        capture_output=True, text=True, encoding="utf-8", errors="replace")
            print(diagnostic.stdout, flush=True)
            raise
        finally:
            failing = sys.exc_info()[0] is not None
            cleanup = subprocess.run([*compose, "down", "--volumes", "--remove-orphans"],
                                     capture_output=True, text=True, encoding="utf-8", errors="replace")
            if cleanup.returncode:
                if failing:
                    print("Cleanup failed: " + cleanup.stderr, flush=True)
                else:
                    raise RuntimeError("Cleanup failed: " + cleanup.stderr)


if __name__ == "__main__":
    main()
