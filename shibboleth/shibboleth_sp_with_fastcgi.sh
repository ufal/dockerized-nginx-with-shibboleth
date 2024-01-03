#!/bin/bash
# https://github.com/ufal/lindat-dspace/wiki/Building-Shibboleth-with-FastCGI-support
# ensure the versions are still latest

apt-get install libfcgi-dev libboost-all-dev openssl libssl-dev pkg-config libcurl4-openssl-dev

INSTALLDIR=/opt/shibboleth-sp

function get {
  local dirname=$1
  local version=$2
  local url=$3
  local archive="$dirname-$version.tar.gz"

  if [ ! -d "$dirname" ]; then
    wget -O "$archive" "$url$archive"
    tar -xzvf "$archive"
    mv `tar -ztf "$archive" | head -n 1` "$dirname.$version"
        ln -s $dirname.$version $dirname
    rm "$archive"
  fi
}

get log4shib 2.0.1 http://shibboleth.net/downloads/log4shib/latest/
get xerces-c 3.2.5 http://mirror.hosting90.cz/apache/xerces/c/3/sources/
get xml-security-c 2.0.4 http://mirror.hosting90.cz/apache/santuario/c-library/
get xmltooling 3.2.4 http://shibboleth.net/downloads/c++-opensaml/latest/
get opensaml 3.2.1 http://shibboleth.net/downloads/c++-opensaml/latest/
get shibboleth-sp 3.4.1 http://shibboleth.net/downloads/service-provider/latest/


function compile {
    local dirname=$1
    local config="--enable-option-checking=fatal $2"

    cd $dirname && \
    ./configure $config && \
    make && \
    make install && \
    cd ..
}

export PKG_CONFIG_PATH=${INSTALLDIR}/lib/pkgconfig
compile log4shib "--disable-static --disable-doxygen --prefix=$INSTALLDIR" && \
compile xerces-c "--disable-netaccessor-curl --prefix=$INSTALLDIR" && \
compile xml-security-c "--without-xalan --disable-static \
  --prefix=$INSTALLDIR" && \
compile xmltooling "-prefix=$INSTALLDIR -C" && \
compile opensaml "--prefix=$INSTALLDIR -C" && \
compile shibboleth-sp "--prefix=$INSTALLDIR \
  --with-fastcgi"
