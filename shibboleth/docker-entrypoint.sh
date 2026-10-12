#!/bin/bash

set -euo pipefail

# envsubst is in gettext-base
# xmllint is in libxml2-utils

# use keys in /sp-keys if they exist, otherwise generate them
mkdir -p /sp-keys
cd /sp-keys
for use in signing encrypt; do
    key="sp-$use-key.pem"
    cert="sp-$use-cert.pem"
    if [[ -f "$key" && -f "$cert" ]]; then
        echo "Using existing SP $use key pair"
    elif [[ -e "$key" || -e "$cert" ]]; then
        echo "Incomplete SP $use key pair in /sp-keys; restore the missing file" >&2
        exit 1
    else
        /opt/shibboleth-sp/etc/shibboleth/keygen.sh -n "sp-$use" -h "${SHIB_HOSTNAME:?SHIB_HOSTNAME must be set}"
    fi
done

# copy keys to /opt/shibboleth-sp/etc/shibboleth
cp -Rv /sp-keys/. /opt/shibboleth-sp/etc/shibboleth/

# if dir /overrides exists, overlay it on top of /opt/shibboleth-sp
if [ -d /overrides ]; then
    echo "Overlaying /overrides on top of /opt/shibboleth-sp"
    cp -Rv /overrides/. /opt/shibboleth-sp
fi

# interpolate templates
my_vars=$(env | cut -d= -f1 | awk -v filter="${FILTER:-}" '$0 ~ filter {printf "${%s} ", $0}')
cd /opt/shibboleth-sp/templates
for template in *.template; do
    [[ -f "$template" ]] || continue
    echo "Interpolating $template"
    envsubst "$my_vars" < $template > /opt/shibboleth-sp/etc/shibboleth/${template%.template}
done

cd /opt/shibboleth-sp/etc/shibboleth

# if md_template.xml does not exist, remove the template attribute from shibboleth2.xml
if [ ! -f md_template.xml ]; then
    echo "Removing md_template attribute from shibboleth2.xml"
    sed -i -e 's# template="md_template.xml"##' shibboleth2.xml
fi

# process xinclude in shibboleth2.xml
echo "Processing xinclude in shibboleth2.xml"
xmllint --xinclude --output shibboleth2.xml shibboleth2.xml

# Validate before supervisor starts endlessly restarting broken services.
/opt/shibboleth-sp/sbin/shibd -t

exec "$@"
