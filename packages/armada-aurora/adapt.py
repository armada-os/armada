#!/usr/bin/env python3
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
for path in (root / "lib/src/main/java").rglob("*.kt"):
    source = path.read_text()
    source = re.sub(
        r"^import (android\.(os.Parcelable|annotation.SuppressLint|util.Log)|kotlinx.parcelize.Parcelize)\n",
        "", source, flags=re.M,
    )
    source = re.sub(r"^@Parcelize\n", "", source, flags=re.M).replace(" : Parcelable", "")
    source = re.sub(r"^\s*@SuppressLint\([^\n]*\)\n", "\n", source, flags=re.M)
    source = re.sub(r"^.*Log\.[de]\(.*\)\n", "", source, flags=re.M)
    source = source.replace("import android.util.Base64", "import java.util.Base64")
    source = source.replace("clusters[cluster.id] = cluster", "clusters[clusters.size] = cluster")
    if path.name == "DeviceInfoProvider.kt":
        source = source.replace('getList("Features"))', 'getList("Features").map { it.substringBefore(\'=\') })')
        source = source.replace('.setName(it)', '.setName(it.substringBefore(\'=\'))').replace('.setValue(0)', '.setValue(it.substringAfter(\'=\', "0").toInt())')
    source = source.replace(
        "Base64.decode(base64EncodedHash, Base64.URL_SAFE)",
        "Base64.getUrlDecoder().decode(base64EncodedHash)",
    )
    source = source.replace(
        "Base64.encodeToString(\n            nonceBytes,\n"
        "            Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING\n        )",
        "Base64.getUrlEncoder().withoutPadding().encodeToString(nonceBytes)",
    )
    if re.search(r"^import (android\.|kotlinx.parcelize)", source, flags=re.M):
        raise SystemExit("Unhandled Android dependency: " + str(path))
    path.write_text(source)
