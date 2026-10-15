#!/bin/bash
set -euxo pipefail

CHUNKAH_LOG_FILE="${RUNNER_TEMP}/chunkah.log"
CHUNKAH_MANIFEST_FILE="${RUNNER_TEMP}/chunkah-manifest.json"
CHUNKAH_IMAGE_CONFIG_FILE="${RUNNER_TEMP}/chunkah-image-config.json"
for component in steam proton; do
if ! grep -Eq "creating tar layer .*\"xattr/${component}\"" "${CHUNKAH_LOG_FILE}"; then
    echo "::error::Chunkah did not emit an xattr/${component} component layer"
    exit 1
fi
done

CHUNKED_REF="oci:${RUNNER_TEMP}/chunked"
skopeo inspect --raw "${CHUNKED_REF}" > "${CHUNKAH_MANIFEST_FILE}"
jq -e '(.layers | length) > 1 and (.layers | length) <= 128' \
"${CHUNKAH_MANIFEST_FILE}" || {
    echo "::error::Chunkah output has an invalid layer count"
    exit 1
}
jq -e '((.annotations // {}) | has("ostree.commit") | not) and
((.annotations // {}) | has("ostree.final-diffid") | not)' \
"${CHUNKAH_MANIFEST_FILE}" || {
    echo "::error::Chunkah output retained OSTree manifest annotations"
    exit 1
}
skopeo inspect --config "${CHUNKED_REF}" > "${CHUNKAH_IMAGE_CONFIG_FILE}"
jq -e --slurpfile expected "${RUNNER_TEMP}/chunkah-config.json" \
'.config == $expected[0]' "${CHUNKAH_IMAGE_CONFIG_FILE}" || {
    echo "::error::Chunkah output did not preserve the prepared runtime config"
    exit 1
}
jq -e '.architecture == "arm64" and .os == "linux" and
    .config.Cmd == ["/sbin/init"] and
    .config.Labels["containers.bootc"] == "1" and
    .config.Labels["ostree.bootable"] == "true" and
    (.config.Labels | has("ostree.commit") | not) and
    (.config.Labels | has("ostree.final-diffid") | not)' \
"${CHUNKAH_IMAGE_CONFIG_FILE}"
python3 build_files/verify-steam-bootstrap.py --oci "${RUNNER_TEMP}/chunked"
echo "Steam bootstrap manifest verified in Chunkah output"
summary=$(jq '{layers: (.layers | length), compressed_bytes: ([.layers[].size] | add)}' \
  "${CHUNKAH_MANIFEST_FILE}")
if [ $1 == "build" ]; then
    printf '%s\n' "$summary"
    echo "ref=${CHUNKED_REF}" >> "${GITHUB_OUTPUT}"
elif [ $1 == "pr" ]; then
    printf '%s\n' "$summary" >> "${GITHUB_STEP_SUMMARY}"
fi
