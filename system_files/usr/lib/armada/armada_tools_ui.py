import re
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk, Pango

import armada_tools as backend


class OperationDialog(Adw.Window):
    def __init__(self, parent, title, on_restart=None):
        super().__init__(transient_for=parent, modal=True, title=title,
                         default_width=520, default_height=240)
        self.running = True
        self.succeeded = False
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar(show_end_title_buttons=False)
        self.heading = Adw.WindowTitle(title=title)
        header.set_title_widget(self.heading)
        box.append(header)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                          margin_top=16, margin_bottom=16, margin_start=24, margin_end=24)
        self.message = Gtk.Label(label="Preparing…", wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                 xalign=0, yalign=0, max_width_chars=48)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                   min_content_height=60, vexpand=True, child=self.message)
        self.progress = Gtk.ProgressBar()
        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.END)
        self.close_button = Gtk.Button(label="Close", sensitive=False)
        self.close_button.connect("clicked", lambda *_: self.close())
        buttons.append(self.close_button)
        self.restart_button = Gtk.Button(label="Restart", visible=False)
        self.restart_button.add_css_class("suggested-action")

        def restart(*_):
            self.close()
            on_restart()
        if on_restart:
            self.restart_button.connect("clicked", restart)
        buttons.append(self.restart_button)
        for child in (scroll, self.progress, buttons):
            content.append(child)
        box.append(content)
        content.set_vexpand(True)
        self.set_content(box)
        self.connect("close-request", lambda *_: self.running)

    def update(self, status):
        if status["code"] is None:
            self.message.set_text(status["message"])
            percentages = re.findall(r"(?m)^(\d{1,3})%$", status["output"])
            if percentages:
                self.progress.set_fraction(min(100, int(percentages[-1])) / 100)
            else:
                self.progress.pulse()

    def finish(self, message, success=False):
        self.running = False
        self.succeeded = success
        self.message.set_text(message)
        self.progress.set_visible(False)
        self.close_button.set_sensitive(True)
        self.close_button.grab_focus()


class UpdatesGroup(Adw.PreferencesGroup):
    def __init__(self, window):
        super().__init__(title="Operating System")
        self.window = window
        self.state = None
        self.loading = False
        self.requesting = False
        self.updating = False
        self.job = backend.CommandJob()
        self.result = ""
        self.channels = []
        self.confirmation = None
        self.current = Adw.ActionRow(title="Current Version", subtitle="Checking…")
        self.previous = Adw.ActionRow(title="Previous Version", subtitle="Checking…")
        for row in (self.current, self.previous):
            row.set_subtitle_selectable(True)
            row.set_subtitle_lines(0)
            self.add(row)
        self.rollback = Gtk.Button(label="Roll Back", sensitive=False, valign=Gtk.Align.CENTER)
        self.rollback.connect("clicked", lambda *_: self.confirm_rollback())
        self.previous.add_suffix(self.rollback)
        self.channel = Adw.ComboRow(title="Update Channel", model=Gtk.StringList.new([]),
                                    use_subtitle=True, subtitle_lines=0, sensitive=False)
        self.channel.connect("notify::selected", self.change_channel)
        self.update = Gtk.Button(label="Update", sensitive=False, valign=Gtk.Align.CENTER)
        self.update.connect("clicked", lambda *_: self.confirm_update())
        self.update.set_tooltip_text("Install the latest OS version from the selected channel")
        self.channel.add_suffix(self.update)
        self.add(self.channel)
        self.operation = None
        self.message = Gtk.Label(wrap=True, xalign=0, selectable=True, margin_top=8, visible=False)
        self.add(self.message)
        self.refresh()

    def show_message(self, message):
        self.message.set_text(message)
        self.message.set_visible(bool(message))

    def poll(self):
        status = self.job.status()
        self.operation.update(status)
        if status["code"] is None:
            return GLib.SOURCE_CONTINUE
        self.requesting = False
        success = status["code"] == 0
        self.operation.finish(status["message"] if success else "Operation failed.\n\n" + status["message"], success=success)
        self.refresh()
        return GLib.SOURCE_REMOVE

    def controls(self, enabled):
        self.rollback.set_sensitive(enabled)
        self.update.set_sensitive(enabled)
        self.channel.set_sensitive(enabled)

    def refresh(self):
        if self.loading or self.requesting:
            return
        self.loading = True
        self.controls(False)

        def completed(state, error):
            self.loading = False
            if error:
                self.controls(False)
                self.show_message(self.result + "\nCould not read OS state: " + error)
                self.window.set_steam_sensitive(not self.window.repair_running)
            else:
                self.render(state)
            return GLib.SOURCE_REMOVE
        self.window.background(lambda: backend.privileged_request("get-os"), completed)

    def render(self, state):
        self.state = state
        idle = not self.requesting and not self.loading
        self.current.set_subtitle(state["booted"]["version"])
        previous = state["rollback"]
        self.previous.set_subtitle(previous["version"] if previous else "No previous version available")
        self.rollback.set_sensitive(idle and bool(previous) and not previous["incompatible"] and not state["rollback_queued"])
        if self.operation and not self.operation.running:
            self.operation.restart_button.set_visible(idle and self.operation.succeeded and state["reboot_ready"])
        self.updating = True
        self.channels = state["channels"]
        self.channel.set_use_subtitle(not self.channels)
        if self.channels:
            self.channel.set_subtitle("")
        self.channel.set_model(Gtk.StringList.new([value.title() for value in self.channels]
                                                 or [state["channel"] or "Unavailable"]))
        if state["channel"] in self.channels:
            self.channel.set_selected(self.channels.index(state["channel"]))
        self.updating = False
        self.channel.set_sensitive(idle)
        self.channel.set_activatable(idle and bool(self.channels))
        self.channel.set_enable_search(False)
        self.update.set_sensitive(idle and bool(state["repository"]))
        if self.result:
            self.show_message(self.result)
        elif state["rollback_queued"]:
            self.show_message("Rollback ready. Restart to apply.")
        elif state["staged"]:
            self.show_message("Update installed. Restart to apply.")
        else:
            self.show_message("")
        if hasattr(self.window, "repair_button"):
            self.window.set_steam_sensitive(idle and not self.window.repair_running)

    def request(self, action, *arguments):
        if self.state is None or self.requesting or self.loading or self.window.repair_running:
            return
        self.result = ""
        if action in {"update-os", "rollback-os"}:
            self.operation = OperationDialog(self.window, "OS Update" if action == "update-os" else "OS Rollback",
                                             on_restart=self.confirm_restart)
            self.operation.present()
            try:
                self.job.start(backend.privileged_command(action, *arguments), "os-operation.log")
            except Exception as error:
                self.operation.finish(f"Could not start: {error}")
                return
            GLib.timeout_add(250, self.poll)
        else:
            def completed(result, error):
                self.requesting = False
                self.result = error or ""
                self.refresh()
                return GLib.SOURCE_REMOVE
            self.window.background(lambda: backend.privileged_request(action, *arguments), completed)
        self.requesting = True
        self.controls(False)
        self.window.set_steam_sensitive(False)
        self.show_message("")

    def confirm(self, heading, body, label, action, *arguments):
        if self.confirmation is not None:
            self.confirmation.present(self.window)
            return
        self.confirmation = Adw.AlertDialog(heading=heading, body=body, prefer_wide_layout=True)
        self.confirmation.add_response("cancel", "Cancel")
        self.confirmation.add_response("proceed", label)
        self.confirmation.set_default_response("cancel")
        self.confirmation.set_close_response("cancel")

        def responded(dialog, response):
            self.confirmation = None
            if response == "proceed":
                self.request(action, *arguments)
        self.confirmation.connect("response", responded)
        self.confirmation.present(self.window)

    def confirm_update(self):
        self.confirm("Update Armada?", "Install the latest available OS version from the currently selected channel.\n\n"
                     "A restart will be needed if an update is installed.", "Update", "update-os")

    def confirm_rollback(self):
        target = self.state["rollback"]
        if not target:
            return
        pending = " The pending update will be discarded." if self.state["staged"] else ""
        self.confirm("Roll Back Armada?", f"Restore version {target['version']} and its system settings. "
                     "Games and personal files are kept."
                     f"{pending}\n\nA restart is required.", "Roll Back", "rollback-os", target["checksum"])

    def confirm_restart(self):
        self.confirm("Restart Now?", "Save your work and close any running games before restarting.", "Restart", "restart-os")

    def change_channel(self, row, *_):
        selected = row.get_selected()
        if self.updating or self.requesting or selected >= len(self.channels):
            return
        channel = self.channels[selected]
        if channel == self.state["channel"]:
            return
        self.request("channel-" + channel)


class ToolsWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Armada Tools", default_width=1100, default_height=620)
        self.set_size_request(360, 280)
        monitors = self.get_display().get_monitors()
        if monitors.get_n_items():
            geometry = monitors.get_item(0).get_geometry()
            self.set_default_size(min(1100, max(360, geometry.width - 32)),
                                  min(620, max(280, geometry.height - 64)))
        self.refreshing = False
        self.ssh_busy = False
        self.updating = False
        self.ssh_state = None
        self.job = backend.SteamJob()
        self.repair_running = False
        self.confirmation = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Armada Tools"))
        box.append(header)
        self.scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.sections_grid = Gtk.Grid(column_spacing=16, row_spacing=16, column_homogeneous=True,
                                      margin_top=12, margin_bottom=12, margin_start=16, margin_end=16)
        clamp = Adw.Clamp(maximum_size=1200, child=self.sections_grid)
        self.scroll.set_child(clamp)
        box.append(self.scroll)
        self.set_content(box)
        self.updates = UpdatesGroup(self)

        repair_group = Adw.PreferencesGroup(title="Steam")
        self.steam_version = Adw.ActionRow(title="Client Version", subtitle="Checking…")
        self.steam_version.set_subtitle_selectable(True)
        self.steam_version.set_tooltip_text("Installed client version from Steam’s package manifest")
        repair_group.add(self.steam_version)
        self.repair_button = Gtk.Button(label="Repair", valign=Gtk.Align.CENTER,
                                         tooltip_text="Reinstall the factory client; keep games and accounts")
        self.repair_button.connect("clicked", lambda *_: self.confirm_repair())
        self.steam_version.add_suffix(self.repair_button)
        self.repair_dialog = None

        ssh_group = Adw.PreferencesGroup(title="Remote Access")
        self.ssh_row = Adw.ActionRow(title="Enable SSH", subtitle="Checking SSH status…")
        self.ssh_row.set_subtitle_lines(0)
        self.ssh_switch = Gtk.Switch(valign=Gtk.Align.CENTER, sensitive=False)
        self.ssh_switch.connect("notify::active", self.change_ssh)
        self.ssh_row.add_suffix(self.ssh_switch)
        self.ssh_row.set_activatable_widget(self.ssh_switch)
        ssh_group.add(self.ssh_row)
        self.connection_row = Adw.ActionRow(title="IP Address", subtitle="Checking…")
        self.connection_row.set_subtitle_selectable(True)
        self.connection_row.set_subtitle_lines(0)
        ssh_group.add(self.connection_row)
        self.ssh_error = Gtk.Label(wrap=True, xalign=0, selectable=True, visible=False)
        self.ssh_error.add_css_class("error")
        ssh_group.add(self.ssh_error)

        info_group = Adw.PreferencesGroup(title="System Information")
        info_grid = Gtk.Grid(column_spacing=12, row_spacing=8,
                             margin_top=12, margin_bottom=12, margin_start=14, margin_end=14)
        self.info_rows = {}
        for index, title in enumerate(("Device", "Kernel", "Storage")):
            label = Gtk.Label(label=title, xalign=0, valign=Gtk.Align.START)
            value = Gtk.Label(label="Checking…", xalign=0, valign=Gtk.Align.START, hexpand=True,
                              wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
            value.add_css_class("dim-label")
            info_grid.attach(label, 0, index, 1, 1)
            info_grid.attach(value, 1, index, 1, 1)
            self.info_rows[title] = value
        info_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_card.add_css_class("card")
        info_card.append(info_grid)
        info_group.add(info_card)
        self.sections = (info_group, ssh_group, self.updates, repair_group)
        self.columns = []
        for sections in (self.sections[:2], self.sections[2:]):
            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                             hexpand=True, valign=Gtk.Align.START)
            for section in sections:
                column.append(section)
            self.columns.append(column)
        self.arrange_sections(2)
        breakpoint = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 759px"))
        breakpoint.connect("apply", lambda *_: self.arrange_sections(1))
        breakpoint.connect("unapply", lambda *_: self.arrange_sections(2))
        self.add_breakpoint(breakpoint)
        self.connect("close-request", self.close_requested)
        self.refresh()

    def arrange_sections(self, columns):
        for column in self.columns:
            if column.get_parent() is self.sections_grid:
                self.sections_grid.remove(column)
        for index, column in enumerate(self.columns):
            self.sections_grid.attach(column, index % columns, index // columns, 1, 1)

    def background(self, work, completed):
        def run():
            try:
                result, error = work(), None
            except Exception as exception:
                result, error = None, str(exception)
            GLib.idle_add(completed, result, error)
        threading.Thread(target=run, daemon=True).start()

    def refresh(self):
        if self.refreshing or self.ssh_busy:
            return
        self.updates.refresh()
        self.refreshing = True
        self.ssh_switch.set_sensitive(False)

        def collect():
            values = {}
            for name, function in (("system", backend.system_info), ("network", backend.connection_info),
                                   ("steam_version", backend.steam_client_version),
                                   ("ssh", lambda: backend.ssh_request("get-ssh"))):
                try:
                    values[name] = function()
                except Exception as error:
                    values[name + "_error"] = str(error)
            return values

        def completed(values, error):
            self.refreshing = False
            if error:
                self.show_ssh_error(error)
                return GLib.SOURCE_REMOVE
            for title, row in self.info_rows.items():
                row.set_text(values.get("system", {}).get(title, "Unavailable"))
            self.steam_version.set_subtitle(values.get("steam_version", "Unknown"))
            addresses = values.get("network", {}).get("addresses", [])
            self.connection_row.set_subtitle(", ".join(address for _, address in addresses)
                                           if addresses else "No network address available")
            if "ssh" in values:
                self.update_ssh(values["ssh"])
                self.show_ssh_error(values.get("network_error", ""))
            else:
                self.ssh_row.set_subtitle("SSH status unavailable")
                self.show_ssh_error(values.get("ssh_error", "Could not read SSH status"))
            return GLib.SOURCE_REMOVE

        self.background(collect, completed)

    def update_ssh(self, state):
        self.ssh_state = state
        self.updating = True
        self.ssh_switch.set_active(state["active"])
        self.updating = False
        running = "Running" if state["active"] else "Stopped"
        self.ssh_row.set_subtitle(running)
        self.ssh_switch.set_sensitive(True)

    def show_ssh_error(self, message):
        self.ssh_error.set_text(message)
        self.ssh_error.set_visible(bool(message))

    def change_ssh(self, switch, *_):
        if self.updating or self.ssh_busy:
            return
        self.set_ssh(switch.get_active())

    def set_ssh(self, enabled):
        self.ssh_busy = True
        self.ssh_switch.set_sensitive(False)
        self.ssh_row.set_subtitle("Updating SSH settings…")
        action = "enable-ssh" if enabled else "disable-ssh"

        def completed(state, error):
            self.ssh_busy = False
            if error:
                if self.ssh_state is not None:
                    self.update_ssh(self.ssh_state)
                self.show_ssh_error(error)
                self.ssh_row.set_subtitle("Could not update SSH settings. Reopen Tools to check the current state.")
            else:
                self.show_ssh_error("")
                self.update_ssh(state)
            return GLib.SOURCE_REMOVE

        self.background(lambda: backend.ssh_request(action), completed)

    def confirm_repair(self):
        if self.repair_running:
            return
        if self.confirmation is not None:
            self.confirmation.present(self)
            return
        self.confirmation = Adw.AlertDialog(prefer_wide_layout=True, heading="Repair Steam?", body=
            "Reinstall the factory Steam client and clear its web cache.\n\n"
            "Your games, saves, accounts, and settings will be kept.")
        self.confirmation.add_response("cancel", "Cancel")
        self.confirmation.add_response("repair", "Repair")
        self.confirmation.set_default_response("cancel")
        self.confirmation.set_close_response("cancel")
        self.confirmation.set_response_appearance("repair", Adw.ResponseAppearance.SUGGESTED)

        def responded(dialog, response):
            self.confirmation = None
            if response == "repair":
                self.start_repair()
        self.confirmation.connect("response", responded)
        self.confirmation.present(self)

    def set_steam_sensitive(self, enabled):
        self.repair_button.set_sensitive(enabled)

    def start_repair(self):
        self.repair_dialog = OperationDialog(self, "Steam Repair")
        self.repair_dialog.present()
        try:
            self.job.start()
        except Exception as error:
            self.repair_dialog.finish(f"Could not start: {error}")
            return
        self.repair_running = True
        self.updates.set_sensitive(False)
        self.set_steam_sensitive(False)
        GLib.timeout_add(250, self.poll_repair)

    def poll_repair(self):
        status = self.job.status()
        self.repair_dialog.update(status)
        if status["code"] is None:
            return GLib.SOURCE_CONTINUE
        self.repair_running = False
        self.steam_version.set_subtitle(backend.steam_client_version())
        self.updates.set_sensitive(True)
        self.set_steam_sensitive(True)
        if status["code"] == 0:
            self.repair_dialog.finish("Steam repair complete.")
        else:
            self.repair_dialog.finish("Steam repair failed.\n\n" + status["message"])
        return GLib.SOURCE_REMOVE

    def close_requested(self, *_):
        if self.repair_running:
            self.repair_dialog.present()
            return True
        if self.updates.requesting or self.updates.loading:
            if self.updates.operation and self.updates.operation.running:
                self.updates.operation.present()
            return True
        if self.ssh_busy:
            self.ssh_row.set_subtitle("Please wait for SSH settings to finish updating.")
            return True
        self.get_application().window = None
        return False


class ToolsApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.armada.Tools")
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        settings = Gtk.Settings.get_default()
        font = Pango.FontDescription.from_string(settings.get_property("gtk-font-name"))
        font.set_size(14 * Pango.SCALE)
        settings.set_property("gtk-font-name", font.to_string())

    def do_activate(self):
        if self.window is None:
            self.window = ToolsWindow(self)
        self.window.present()



def main():
    return ToolsApplication().run([sys.argv[0]])
