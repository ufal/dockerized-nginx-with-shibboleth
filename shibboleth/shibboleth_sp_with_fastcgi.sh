#!/bin/bash
set -euo pipefail

INSTALLDIR=/opt/shibboleth-sp

function get {
  local dirname=$1
  local version=$2
  local url=$3
  local checksum=$4
  local archive="$dirname-$version.tar.gz"

  if [ ! -d "$dirname" ]; then
    wget -O "$archive" "$url$archive"
    printf '%s  %s\n' "$checksum" "$archive" | sha256sum -c -
    tar -xzvf "$archive"
    ln -s "$dirname-$version" "$dirname"
    rm "$archive"
  fi
}

# Use immutable HTTPS release paths; old releases disappear from /latest/.
get log4shib 2.0.1 https://shibboleth.net/downloads/log4shib/2.0.1/ aad37f3929bd3d4c16f09831ff109c20ae8c7cb8b577917e3becb12f873f26df
get xerces-c 3.3.0 https://archive.apache.org/dist/xerces/c/3/sources/ 9555f1d06f82987fbb4658862705515740414fd34b4db6ad2ed76a2dc08d3bde
get xml-security-c 3.0.0 https://shibboleth.net/downloads/xml-security-c/3.0.0/ 5976ba9e72cbb61bd70df3f91d064ffcec8d0b3ba39c5cf4856f96f9efeb9a76
get xmltooling 3.3.0 https://shibboleth.net/downloads/c++-opensaml/3.3.1/ 1a8a4eb6e48e7eb3546966ed025bfcb785b0d78e14225086fa4eb00eba4d0952
get opensaml 3.3.1 https://shibboleth.net/downloads/c++-opensaml/3.3.1/ 9d0716d52d4f14e53b1b19de499387e2235ef8115e8feca1ba12a4e2fd50d046
get shibboleth-sp 3.6.0 https://shibboleth.net/downloads/service-provider/3.6.0/ ed0c0a2964c1c36fbbd35f6f591ee30c5b2199328f4290962d55b89cba2508b0


function compile {
    local dirname=$1
    local config="--enable-option-checking=fatal $2"

    cd $dirname && \
    ./configure $config && \
    make -j"${BUILD_JOBS:-4}" && \
    make install NOKEYGEN=1 && \
    cd ..
}

export PKG_CONFIG_PATH=${INSTALLDIR}/lib/pkgconfig
compile log4shib "--disable-static --disable-doxygen --prefix=$INSTALLDIR" && \
compile xerces-c "--disable-netaccessor-curl --prefix=$INSTALLDIR" && \
compile xml-security-c "--disable-static --prefix=$INSTALLDIR" && \
compile xmltooling "-prefix=$INSTALLDIR -C" && \
compile opensaml "--prefix=$INSTALLDIR -C" && \
compile shibboleth-sp "--prefix=$INSTALLDIR --with-fastcgi --disable-apache-24 --disable-odbc"
