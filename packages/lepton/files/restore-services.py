#!/usr/bin/env python3
# Start the SystemServer services Lepton comments out (clipboard, restrictions,
# biometric + auth, NSD, cross-profile apps, hardware properties); apps that
# expect them, SDL ones first, crash on the null manager.
# Adapted from SteamOS-ARM-Handhelds (GPL-2.0, hashtagbasit).
import sys
p = sys.argv[1]
s = open(p).read()
anchor = '    const-string v0, "AppServiceManager"\n'
assert s.count(anchor) == 1, "anchor"
SSM = "Lcom/android/server/SystemServer;->mSystemServiceManager:Lcom/android/server/SystemServiceManager;"
START = "Lcom/android/server/SystemServiceManager;->startService(Ljava/lang/Class;)Lcom/android/server/SystemService;"
block = "    # armada: restored services\n"
for cls in ("Lcom/android/server/clipboard/ClipboardService;",
            "Lcom/android/server/restrictions/RestrictionsManagerService;",
            # BiometricService before AuthService, which binds to it at start
            # (stock Android only starts it with fingerprint/face hardware).
            "Lcom/android/server/biometrics/BiometricService;",
            "Lcom/android/server/biometrics/AuthService;",
            "Lcom/android/server/pm/CrossProfileAppsService;"):
    block += f"""    :armada_try_{cls.split('/')[-1][:-1]}_start
    iget-object v0, v2, {SSM}
    const-class v1, {cls}
    invoke-virtual {{v0, v1}}, {START}
    :armada_try_{cls.split('/')[-1][:-1]}_end
    .catchall {{:armada_try_{cls.split('/')[-1][:-1]}_start .. :armada_try_{cls.split('/')[-1][:-1]}_end}} :armada_catch_{cls.split('/')[-1][:-1]}
    goto :armada_done_{cls.split('/')[-1][:-1]}
    :armada_catch_{cls.split('/')[-1][:-1]}
    move-exception v0
    :armada_done_{cls.split('/')[-1][:-1]}

"""
block += """    :armada_try_nsd_start
    iget-object v0, v2, Lcom/android/server/SystemServer;->mSystemContext:Landroid/content/Context;
    invoke-static {v0}, Lcom/android/server/NsdService;->create(Landroid/content/Context;)Lcom/android/server/NsdService;
    move-result-object v1
    const-string v0, "servicediscovery"
    invoke-static {v0, v1}, Landroid/os/ServiceManager;->addService(Ljava/lang/String;Landroid/os/IBinder;)V
    :armada_try_nsd_end
    .catchall {:armada_try_nsd_start .. :armada_try_nsd_end} :armada_catch_nsd
    goto :armada_done_nsd
    :armada_catch_nsd
    move-exception v0
    :armada_done_nsd

    :armada_try_hwprops_start
    new-instance v1, Lcom/android/server/HardwarePropertiesManagerService;
    iget-object v0, v2, Lcom/android/server/SystemServer;->mSystemContext:Landroid/content/Context;
    invoke-direct {v1, v0}, Lcom/android/server/HardwarePropertiesManagerService;-><init>(Landroid/content/Context;)V
    const-string v0, "hardware_properties"
    invoke-static {v0, v1}, Landroid/os/ServiceManager;->addService(Ljava/lang/String;Landroid/os/IBinder;)V
    :armada_try_hwprops_end
    .catchall {:armada_try_hwprops_start .. :armada_try_hwprops_end} :armada_catch_hwprops
    goto :armada_done_hwprops
    :armada_catch_hwprops
    move-exception v0
    :armada_done_hwprops

"""
if "# armada: restored services" not in s:
    s = s.replace(anchor, block + anchor)
open(p, "w").write(s)
