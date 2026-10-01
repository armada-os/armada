#!/usr/bin/env python3
# repack-jar.py ORIG.jar OUT.jar name=file... -- replace entries, keep every
# entry stored and 4-byte aligned like zipalign (ART mmaps dex in place).
# From SteamOS-ARM-Handhelds (GPL-2.0, hashtagbasit).
import sys, zipfile, zlib, struct
orig, out = sys.argv[1:3]
repl = dict(a.split("=", 1) for a in sys.argv[3:])
zin = zipfile.ZipFile(orig)
with open(out, "wb") as f:
    zout = zipfile.ZipFile(f, "w", zipfile.ZIP_STORED)
    for info in zin.infolist():
        data = open(repl[info.filename], "rb").read() if info.filename in repl else zin.read(info)
        zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
        zi.compress_type = zipfile.ZIP_STORED
        zi.external_attr = info.external_attr
        # header = 30 + name + extra; pad extra so data starts 4-aligned
        hdr = f.tell() + 30 + len(info.filename.encode())
        pad = (-hdr) % 4
        zi.extra = b"\0" * pad
        zout.writestr(zi, data)
    zout.close()
z = zipfile.ZipFile(out)
for i in z.infolist():
    assert i.compress_type == 0
    assert (i.header_offset + 30 + len(i.filename.encode()) + len(i.extra)) % 4 == 0, i.filename
print("ok", out)
