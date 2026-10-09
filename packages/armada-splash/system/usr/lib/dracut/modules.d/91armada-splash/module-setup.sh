#!/bin/bash
# Initramfs splash: drm/msm has no cont-splash handoff and blanks the panel
# on bind (~3s); this paints the sail until the realroot splash takes over.

check() {
    # 255 = explicit --add only: the splash binary is installed after the
    # kernel build step, so auto-inclusion there would silently drop it.
    [[ -x "${dracutsysrootdir:-}/usr/libexec/armada/armada-splash" ]] || return 1
    return 255
}

depends() {
    echo systemd bash
    return 0
}

install() {
    inst_multiple \
        /usr/libexec/armada/armada-splash \
        /usr/libexec/armada/armada-splash-launcher \
        /usr/libexec/armada/device-env \
        /usr/share/armada/splash/splash.asp \
        /usr/share/armada/splash/font.ttf \
        tr cat sleep

    local f
    for f in "${dracutsysrootdir:-}"/usr/lib/armada/devices/*.conf; do
        [[ -e "$f" ]] || continue
        inst_simple "${f#"${dracutsysrootdir:-}"}"
    done

    inst_simple "$moddir/armada-splash-initrd.service" \
        "$systemdsystemunitdir/armada-splash-initrd.service"
    mkdir -p "$initdir/$systemdsystemunitdir/initrd.target.wants"
    ln_r "$systemdsystemunitdir/armada-splash-initrd.service" \
        "$systemdsystemunitdir/initrd.target.wants/armada-splash-initrd.service"

    # Pull the splash from a unit that always runs: systemd does not schedule
    # the dangling initrd.target.wants entry before switch-root on its own.
    mkdir -p "$initdir/$systemdsystemunitdir/dracut-pre-mount.service.d"
    printf '[Unit]\nWants=armada-splash-initrd.service\n' \
        > "$initdir/$systemdsystemunitdir/dracut-pre-mount.service.d/armada-splash.conf"
}
