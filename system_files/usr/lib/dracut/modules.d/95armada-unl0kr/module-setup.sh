#!/bin/bash
# unl0kr as a systemd password agent in the initrd, so the LUKS root can be
# unlocked on the touchscreen. Translated from the upstream mkinitcpio hook
# (sd-unl0kr).

check() {
    return 255
}

depends() {
    echo systemd bash udev-rules
    return 0
}

install() {
    inst_binary /usr/bin/unl0kr
    inst_binary /usr/libexec/unl0kr-agent

    # Default base config from the unl0kr package
    inst_simple /etc/unl0kr.conf

    # Overrides (theming, screen rotation)
    inst_multiple -o /etc/unl0kr.conf.d/*

    inst_simple "$systemdsystemunitdir/unl0kr-agent.service"
    inst_simple "$systemdsystemunitdir/unl0kr-agent.path"

    mkdir -p "$initdir/$systemdsystemunitdir/sysinit.target.wants"
    ln_r "$systemdsystemunitdir/unl0kr-agent.path" \
        "$systemdsystemunitdir/sysinit.target.wants/unl0kr-agent.path"

    # Displace the console agent rather than race it for the VT.
    mkdir -p "$initdir/$systemdsystemunitdir/unl0kr-agent.path.d"
    cat > "$initdir/$systemdsystemunitdir/unl0kr-agent.path.d/armada.conf" <<-CONF
	[Unit]
	Conflicts=systemd-ask-password-console.path
	After=systemd-ask-password-console.path
	CONF

    # Add override for per-device rotation, generated at boot from device-env.
    inst_script "$moddir/armada-unl0kr-config" \
        /usr/libexec/armada/armada-unl0kr-config
    inst_simple "$moddir/armada-unl0kr-config.service" \
        "$systemdsystemunitdir/armada-unl0kr-config.service"
    mkdir -p "$initdir/$systemdsystemunitdir/initrd.target.wants"
    ln_r "$systemdsystemunitdir/armada-unl0kr-config.service" \
        "$systemdsystemunitdir/initrd.target.wants/armada-unl0kr-config.service"

    # device-env is bash and reads /sys/firmware/devicetree/base/model, but it
    # needs tr, sed and grep. Installing those too.
    inst_multiple /usr/lib/armada/devices/*.conf
    inst_multiple tr sed grep

    # libinput's udev helpers and data. Without these, libinput sees no inputs.
    inst_simple /usr/lib/udev/hwdb.bin
    inst_multiple /usr/lib/udev/libinput-device-group \
                  /usr/lib/udev/libinput-fuzz-extract \
                  /usr/lib/udev/libinput-fuzz-to-zero
    inst_rules 60-evdev.rules \
               60-input-id.rules \
               65-libwacom.rules \
               70-mouse.rules \
               70-touchpad.rules \
               80-libinput-device-groups.rules \
               90-libinput-fuzz-override.rules
    inst_multiple -o /usr/share/libinput/*
    inst_multiple -o /usr/share/X11/xkb/*/* /usr/share/X11/xkb/*/*/*

    # Touchscreen drivers
    instmods "=drivers/input/touchscreen"
}
