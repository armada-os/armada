#!/bin/bash
set -euxo pipefail

# useradd misses groups defined in /usr/lib/group.
systemd-sysusers
for group in wheel video render input audio seat gamemode; do
    gid=$(getent group "$group" | cut -d: -f3)
    [[ -n "$gid" ]] || { echo "ERROR: missing group: $group" >&2; exit 1; }
    if ! grep -q "^${group}:" /etc/group; then
        echo "${group}:x:${gid}:armada" >> /etc/group
    elif ! id -nG armada | grep -qw "$group"; then
        gpasswd -a armada "$group"
    fi
done

install -d -m 0700 -o armada -g armada /var/home/armada
chmod 0700 /var/home/armada
install -Dpm 0755 -o armada -g armada \
    /usr/share/applications/armada-return-to-gamemode.desktop \
    /var/home/armada/Desktop/armada-return-to-gamemode.desktop
cp -af /etc/skel/. /var/home/armada/
chown -R armada:armada /var/home/armada

echo 'armada:armada' | chpasswd

cat > /etc/sudoers.d/armada-user <<'EOF'
%wheel ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart sddm
%wheel ALL=(ALL) NOPASSWD: /usr/bin/systemctl start sddm
%wheel ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop sddm
%wheel ALL=(ALL) NOPASSWD: /usr/bin/systemctl poweroff
%wheel ALL=(ALL) NOPASSWD: /usr/bin/systemctl reboot
%wheel ALL=(ALL) NOPASSWD: /usr/libexec/armada/session-control switch-desktop
%wheel ALL=(ALL) NOPASSWD: /usr/libexec/armada/session-control switch-gamemode
%wheel ALL=(ALL) NOPASSWD: /usr/libexec/armada/session-control default-gamemode
%wheel ALL=(ALL) NOPASSWD: /usr/libexec/armada/armada-installer *
EOF
chmod 0440 /etc/sudoers.d/armada-user
