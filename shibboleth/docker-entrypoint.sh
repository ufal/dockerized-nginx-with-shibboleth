#!/bin/bash

set -e

# envsubst is in gettext-base
# xmllint is in libxml2-utils

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

# process xinclude in shibboleth2.xml
cd /opt/shibboleth-sp/etc/shibboleth
echo "Processing xinclude in shibboleth2.xml"
xmllint --xinclude --output shibboleth2.xml shibboleth2.xml

exec "$@"