import os


# Decky's loader is a PyInstaller bundle that exports its unpack dir as
# LD_LIBRARY_PATH, so a spawned script loads bundled libs and /usr/bin/bash dies.
def clean_env(extra=None):
    env = dict(os.environ)
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original:
        env["LD_LIBRARY_PATH"] = original
    else:
        env.pop("LD_LIBRARY_PATH", None)
    if extra:
        env.update(extra)
    return env
