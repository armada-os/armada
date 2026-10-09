#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 [fedora release]"
  exit 1
}

PACKAGES="
glibc-devel.i686
glibc-devel.x86_64
kernel-headers.x86_64
libstdc++.i686
libstdc++.x86_64
libstdc++-devel.i686
libstdc++-devel.x86_64
"

if [ "$#" -eq 0 ]; then
  # shellcheck source=/dev/null
  FEDORA="$(. /etc/os-release && echo "$VERSION_ID")"
elif [ "$#" -ne 1 ]; then
  usage
else
  case "$1" in
      -h|--help)
          usage
          ;;
      [0-9]*)
          FEDORA="$1"
          ;;
      *)
	  usage
	  ;;
  esac
fi


DATE="$(TZ=UTC date +%Y%m%d)"
PKG="fex-sysroot-fc${FEDORA}-${DATE}.tar.gz"
PKGPATH="${PWD}/${PKG}"

cd "$(dirname "$0")"

WORKDIR="$(mktemp -d)"
trap 'rm -rf $WORKDIR' EXIT

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR/sysroot" "$WORKDIR/rpms"

echo
echo "### Downloading packages"
echo "$PACKAGES" | xargs \
  dnf download --destdir="$WORKDIR/rpms" \
    --repo=fedora --repo=updates --releasever="$FEDORA" \
    --forcearch=x86_64 --best

echo
echo "### Extracting packages"
for i in "${WORKDIR}/rpms"/*.rpm; do
    rpm="$(basename "$i")"
    rpmdev-extract -C "${WORKDIR}/rpms" "$i"
    cp -ra "${WORKDIR}/rpms/${rpm%%.rpm}"/* "${WORKDIR}/sysroot/"
done

# Hack to make clang tooling find the right headers
GCCBASE="$(ls -d "${WORKDIR}/sysroot/usr/lib/gcc/x86_64-redhat-linux/"* )"
mkdir -p "${GCCBASE}/32"
touch "${GCCBASE}/crtbegin.o" "${GCCBASE}/32/crtbegin.o"

ln -sr "${WORKDIR}/sysroot/usr/lib/libstdc++.so.6" "${GCCBASE}/32/libstdc++.so"
ln -sr "${WORKDIR}/sysroot/usr/lib64/libstdc++.so.6" "${GCCBASE}/libstdc++.so"

echo
echo "### Extracting license"
# Generate license expression for source file
LICENSE="$(
    rpm -q --queryformat "( %{license} ) AND\n" "${WORKDIR}/rpms"/*.rpm |
    sort | uniq | tr -d '\n' | sed 's/ AND$//'
)"

echo
echo "### Building tarball"
tar czf "$PKGPATH" --sort=name --mtime="${DATE}Z" --group=0 --owner=0 -C "$WORKDIR" sysroot
echo

echo "%global sysroot_version fc${FEDORA}-${DATE}" > fex-sysroot-macros.inc
echo "%global sysroot_license $LICENSE" >> fex-sysroot-macros.inc

echo "Built package: $PKG"
echo
echo "### Done. Don't forget to commit the fex-sysroot-macros.inc file."
