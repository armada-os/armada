#!/bin/bash
# Turn a built Proton tree into a remote payload under a stable tool name, so games mapped
# to it keep the mapping across updates. Steam finds it through STEAM_EXTRA_COMPAT_TOOLS_PATHS.
# usage: package.sh <proton tree> <payload dir> <tool name> <display name>
set -euo pipefail

src=$1 dest=$2 name=$3 label=$4
[[ -x "$src/proton" && -f "$src/toolmanifest.vdf" ]] || { echo "$src is not a Proton tree" >&2; exit 1; }
rm -rf "$dest"
mkdir -p "$dest"
cp -a "$src" "$dest/$name"
cat >"$dest/$name/compatibilitytool.vdf" <<VDF
"compatibilitytools"
{
  "compat_tools"
  {
    "$name"
    {
      "install_path" "."
      "display_name" "$label"
      "from_oslist" "windows"
      "to_oslist" "linux"
    }
  }
}
VDF
