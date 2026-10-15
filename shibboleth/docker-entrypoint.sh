#!/bin/bash

set -e

# envsubst is in gettext-base
# xmllint is in libxml2-utils

# use keys in /sp-keys if they exist, otherwise generate them
cd /sp-keys
/opt/shibboleth-sp/etc/shibboleth/keygen.sh -n sp-signing || true
/opt/shibboleth-sp/etc/shibboleth/keygen.sh -n sp-encrypt || true   

# copy keys to /opt/shibboleth-sp/etc/shibboleth
cp -Rv /sp-keys/. /opt/shibboleth-sp/etc/shibboleth/

# if dir /overrides exists, overlay it on top of /opt/shibboleth-sp
if [ -d /overrides ]; then
    echo "Overlaying /overrides on top of /opt/shibboleth-sp"
    cp -Rv /overrides/. /opt/shibboleth-sp
fi

# interpolate templates
my_vars=$(printf '${%s} ' $(env | cut -d= -f1 | grep "${FILTER:-}"))
cd /opt/shibboleth-sp/templates
for template in $(ls *.template); do
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

exec "$@"