#!/usr/bin/env bash
#
# bin_steam.sh - launcher script for Steam on Linux
# Copyright Valve Corporation. All rights reserved
#
# This is the Steam script that typically resides in /usr/bin
# It will create the Steam bootstrap if necessary and then launch steam.

# verbose
#set -x

set -e

# Get the full name of this script
STEAMSCRIPT="$(cd "${0%/*}" && echo "$PWD")/${0##*/}"
export STEAMSCRIPT
bootstrapscript="$(readlink -f "$STEAMSCRIPT")"
bootstrapdir="$(dirname "$bootstrapscript")"
log_opened=

log () {
    echo "bin_steam.sh[$$]: $*" >&2 || :
}

export STEAMSCRIPT_VERSION=1.0.0.85

# Set up domain for script localization
export TEXTDOMAIN=steam

function show_message()
{
	style=$1
	shift

	case "$style" in
	--error)
		title=$"Error"
		;;
	--warning)
		title=$"Warning"
		;;
	*)
		title=$"Note"
		;;
	esac

	log "$title: $*"

	if [ "${XDG_CURRENT_DESKTOP}" == "gamescope" ]; then
		return
	fi

	if ! zenity "$style" --text="$*" 2>/dev/null; then
		# Save the prompt in a temporary file because it can have newlines in it
		tmpfile="$(mktemp || echo "/tmp/steam_message.txt")"
		echo -e "$*" >"$tmpfile"
		xterm -T "$title" -e "cat $tmpfile; echo -n 'Press enter to continue: '; read input"
		rm -f "$tmpfile"
	fi
}

# Keep in sync with the function of the same name in steam.sh
# Usage: maybe_open_log $STEAM_RUNTIME_SCOUT ~/.steam/steam "$*"
# Uses globals: log_opened + environment variables set by srt-logger
function maybe_open_log()
{
	local srt="$1"
	local data="$2"
	local argv="$3"

	case " $argv " in
		(*\ -srt-logger-opened\ *)
			log "Log already open"
			return 0
			;;
	esac

	if [ -n "$log_opened" ]; then
		return 0
	fi

	if [ "${STEAM_RUNTIME_LOGGER-}" = "0" ]; then
		# Interferes with vscode's gdb wrapping for instance
		log "Logging to console-linux.txt disabled via STEAM_RUNTIME_LOGGER"
		return 0
	fi

	if [ "x${DEBUGGER-}" != "x" ]; then
		# Interferes with ncurses (cgdb etc.)
		log "Setting up for debugging, not logging to console-linux.txt"
		return 0
	fi

	local log_folder="${STEAM_CLIENT_LOG_FOLDER:-logs}"

	# Avoid using mkdir -p here: if ~/.steam/steam is somehow missing,
	# we don't want to create it as a real directory
	if [ -d "$data/$log_folder" ] || mkdir "$data/$log_folder"; then
		log_dir="$data/$log_folder"
	else
		log "Couldn't create $data/$log_folder, not logging to console-linux.txt"
		return 0
	fi

	if source "${srt}/usr/libexec/steam-runtime-tools-0/logger-0.bash" \
		--log-directory="$log_dir" \
		--filename=console-linux.txt \
		--parse-level-prefix \
		-t steam \
	; then
		log_opened=1
	else
		log "Couldn't set up srt-logger, not logging to console-linux.txt"
	fi
}

function detect_platform()
{
	# Maybe be smarter someday
	# Right now this is the only platform we have a bootstrap for, so hard-code it.
	echo steamrtarm64
}

function setup_variables()
{
	# 'steam' or sometimes 'steambeta'
	STEAMPACKAGE="${0##*/}"

	if [ "$STEAMPACKAGE" = bin_steam.sh ]; then
		STEAMPACKAGE=steam
	fi

	STEAMCONFIG=~/.steam
	# ~/.steam/steam or ~/.steam/steambeta
	STEAMDATALINK="$STEAMCONFIG/$STEAMPACKAGE"
	STEAMBOOTSTRAP=steam.sh
	# User-controlled, often ~/.local/share/Steam or ~/Steam
	LAUNCHSTEAMDIR="$(readlink -e -q "$STEAMDATALINK" || true)"
	# Normally 'ubuntu12_32'
	LAUNCHSTEAMPLATFORM="$(detect_platform)"
	# Often in /usr/lib/steam
	LAUNCHSTEAMBOOTSTRAPFILE="$bootstrapdir/bootstraplinux_$LAUNCHSTEAMPLATFORM.tar.xz"
	if [ ! -f "$LAUNCHSTEAMBOOTSTRAPFILE" ]; then
		LAUNCHSTEAMBOOTSTRAPFILE="/usr/lib/$STEAMPACKAGE/bootstraplinux_$LAUNCHSTEAMPLATFORM.tar.xz"
	fi

	# Get the default data path
	STEAM_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
	case "$STEAMPACKAGE" in
		steam)
			CLASSICSTEAMDIR="$HOME/Steam"
			DEFAULTSTEAMDIR="$STEAM_DATA_HOME/Steam"
			;;
		steambeta)
			CLASSICSTEAMDIR="$HOME/SteamBeta"
			DEFAULTSTEAMDIR="$STEAM_DATA_HOME/SteamBeta"
			;;
		*)
			log $"Unknown Steam package '$STEAMPACKAGE'"
			exit 1
			;;
	esac

	# Create the config directory if needed
	if [[ ! -d "$STEAMCONFIG" ]]; then
		mkdir "$STEAMCONFIG"
	fi
}

function install_bootstrap()
{
	STEAMDIR="$1"

	# Save the umask and set strong permissions
	omask="$(umask)"
	umask 0077

	log $"Setting up Steam content in $STEAMDIR"
	mkdir -p "$STEAMDIR"
	cd "$STEAMDIR"
	if ! tar xJf "$LAUNCHSTEAMBOOTSTRAPFILE" ; then
		log $"Failed to extract $LAUNCHSTEAMBOOTSTRAPFILE, aborting installation."
		exit 1
	fi
	ln -fns "$STEAMDIR" "$STEAMDATALINK"
	setup_variables

	# put the Steam icon on the user's desktop
	# try to read ~/.config/user-dirs.dirs to get the current desktop configuration
	# http://www.freedesktop.org/wiki/Software/xdg-user-dirs
	# shellcheck source=/dev/null
	test -f "${XDG_CONFIG_HOME:-$HOME/.config}/user-dirs.dirs" && source "${XDG_CONFIG_HOME:-$HOME/.config}/user-dirs.dirs"
	DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"

	if [ -d "$DESKTOP_DIR" ] && [ "$bootstrapdir" = "/usr/lib/$STEAMPACKAGE" ]; then
		# There might be a symlink in place already, in such case we do nothing
		if [ ! -L "$DESKTOP_DIR/$STEAMPACKAGE.desktop" ]; then
			cp "$bootstrapdir/$STEAMPACKAGE.desktop" "$DESKTOP_DIR"
			# Older .desktop implementations used the execute bits as
			# a marker for a .desktop being safe to treat as a shortcut
			chmod a+x "$DESKTOP_DIR/$STEAMPACKAGE.desktop"
			if command -v gio >/dev/null; then
				# Making it executable is not enough in recent
				# (Ubuntu 20.04) versions of
				# https://gitlab.gnome.org/World/ShellExtensions/desktop-icons
				gio set --type=string "$DESKTOP_DIR/$STEAMPACKAGE.desktop" metadata::trusted true || :
				# Generate an inotify event so the desktop
				# implementation reloads it
				touch "$DESKTOP_DIR/$STEAMPACKAGE.desktop"
			fi
		fi
	fi

	# Restore the umask
	umask "$omask"
}

function repair_bootstrap()
{
	ln -fns "$1" "$STEAMDATALINK"
	setup_variables
}

function check_bootstrap()
{
	local data="$1"
	# Normally we would look for ubuntu12_32/steam-runtime in
	# ~/.steam/root rather than ~/.steam/steam if different, but in
	# this script we assume that ~/.steam/steam and ~/.steam/root
	# are the same: they only differ in developer use-cases which
	# also bypass this script
	local srt="${STEAM_RUNTIME_SCOUT:-"$data/steamrtarm64/steam-runtime"}"
	local argv="$2"

	if [[ -n "$data" && -x "$data/$STEAMBOOTSTRAP" ]]; then
		# Looks good...
		maybe_open_log "$srt" "$data" "$argv"
		return 0
	else
		return 1
	fi
}

function forward_command_line()
{
	if ! [ -p "$STEAMCONFIG/steam.pipe" ]; then
		return 1
	fi

	local runtime="$STEAMCONFIG/root/steamrtarm64"
	local remote="$runtime/steam"

	if [ -x "$remote" ] && "$remote" "$@" 2>/dev/null; then
		return 0
	else
		return 1
	fi
}

# Don't allow running as root
if [ "$(id -u)" == "0" ]; then
	show_message --error $"Cannot run as root user"
	exit 1
fi

# Look for the Steam data files
setup_variables

# If Steam is already running, try to forward the command-line to it.
# If successful, there's nothing more to do.
#if forward_command_line "$@"; then
#	exit 0
#fi

exec "$LAUNCHSTEAMDIR/$LAUNCHSTEAMPLATFORM/steam" "$@"
