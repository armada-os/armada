#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
source BASE.env

# jmods lets us bundle a small JVM rather than require host Java at runtime.
dnf -y install \
  java-25-openjdk-devel java-25-openjdk-jmods \
  rpm-build curl python3 tar gzip
export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")"

rm -rf out
mkdir -p out
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

archive="$work/gplayapi.tar.gz"
curl --fail --location --retry 3 \
  "https://gitlab.com/AuroraOSS/gplayapi/-/archive/${GPLAYAPI_COMMIT}/gplayapi-${GPLAYAPI_COMMIT}.tar.gz" \
  -o "$archive"
printf '%s  %s\n' "$GPLAYAPI_SHA256" "$archive" | sha256sum --check --strict
mkdir -p "$work/source/src/main/kotlin"
tar -xzf "$archive" --strip-components=1 -C "$work/source"

# Adapt Android-only APIs for the host JVM and add Armada's JSON helper.
python3 adapt.py "$work/source"
cp build.gradle.kts settings.gradle.kts "$work/source/"
cp Main.kt "$work/source/src/main/kotlin/"
printf 'org.gradle.jvmargs=-Xmx2g\n' >"$work/source/gradle.properties"
(
  cd "$work/source"
  ./gradlew --no-daemon installDist --console=plain
)

cp -a "$work/source/build/install/armada-aurora" "$work/"
cp "$work/source/LICENSE" "$work/armada-aurora/"
cp -a "$work/source/LICENSES" "$work/armada-aurora/"

sed -i '/^APP_HOME=/a JAVA_HOME="$APP_HOME/runtime"' "$work/armada-aurora/bin/armada-aurora"
"$JAVA_HOME/bin/jlink" \
  --add-modules java.base,java.net.http,java.logging,java.naming,jdk.crypto.ec,jdk.unsupported \
  --strip-debug --no-header-files --no-man-pages \
  --output "$work/armada-aurora/runtime"

rpmbuild -bb \
  --define "_sourcedir $work" \
  --define "_rpmdir $PWD/out" \
  armada-aurora.spec
mv out/aarch64/*.rpm out/
rmdir out/aarch64
