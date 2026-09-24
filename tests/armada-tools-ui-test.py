#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
loader = importlib.machinery.SourceFileLoader("tools_ui", str(ROOT / "system_files/usr/lib/armada/armada_tools_ui.py"))
ui = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(ui)
ui.Gtk.init()
ui.Gtk.Settings.get_default().set_property("gtk-font-name", "Sans 10")
ui.Gtk.Settings.get_default().set_property("gtk-xft-dpi", 96 * 1024)


def wait_for(condition):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        while ui.GLib.MainContext.default().pending():
            ui.GLib.MainContext.default().iteration(False)
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("UI operation did not complete")


def respond(dialog, response):
    label = dialog.get_response_label(response)
    def find(widget):
        if isinstance(widget, ui.Gtk.Button) and widget.get_label() == label:
            return widget
        child = widget.get_first_child()
        while child:
            if button := find(child):
                return button
            child = child.get_next_sibling()
    button = find(dialog)
    assert button is not None, label
    button.emit("clicked")


def check_confirmation(dialog):
    buttons = {}
    def collect(widget):
        if isinstance(widget, ui.Gtk.Button) and widget.get_label() in {"Cancel", "Roll Back", "Update", "Repair"}:
            buttons[widget.get_label()] = widget
        child = widget.get_first_child()
        while child:
            collect(child)
            child = child.get_next_sibling()
    wait_for(dialog.get_mapped)
    collect(dialog)
    until = time.monotonic() + 0.2
    wait_for(lambda: time.monotonic() >= until)
    assert len(buttons) == 2, buttons
    bounds = [button.compute_bounds(dialog)[1] for button in buttons.values()]
    assert abs(bounds[0].get_y() - bounds[1].get_y()) < 1, [(b.get_x(), b.get_y()) for b in bounds]
    assert dialog.get_height() <= window.get_height(), (dialog.get_width(), dialog.get_height())


state = {"active": False, "enabled_at_boot": True}
calls = []
fail_ssh = False


def ssh(action):
    calls.append(action)
    if fail_ssh:
        raise RuntimeError("SSH service unavailable")
    if action != "get-ssh":
        state.update(active=action == "enable-ssh", enabled_at_boot=action == "enable-ssh")
    return dict(state)


os_state = {
    "booted": {"version": "20260919.current"},
    "rollback": {"version": "20260907.previous", "checksum": "b" * 64, "incompatible": False},
    "staged": None, "rollback_queued": False, "reboot_ready": False,
    "channel": "stable", "channels": ["stable", "beta", "preview"],
    "repository": "ghcr.io/armada-os/armada",
}
os_calls = []
operation_script = None
fail_operation = False


def os_command(action, *arguments):
    if not fail_operation:
        os_request(action, *arguments)
    return [str(operation_script), "1" if fail_operation else "0"]


def os_request(action, *arguments):
    import copy
    os_calls.append((action, arguments))
    if action == "get-os":
        return copy.deepcopy(os_state)
    if action.startswith("channel-"):
        os_state["channel"] = action.removeprefix("channel-")
        return {"ok": True}
    if action == "update-os":
        os_state["staged"] = {"version": "20260920.next"}
        os_state["reboot_ready"] = True
        return {"ok": True, "started": 124}
    if action == "rollback-os":
        os_state["staged"] = None
        os_state["rollback_queued"] = True
        os_state["reboot_ready"] = True
        return {"ok": True, "started": 125}
    if action == "restart-os":
        return {"ok": True}
    raise AssertionError(action)


with tempfile.TemporaryDirectory() as directory, \
        patch.object(ui.backend, "ssh_request", side_effect=ssh), \
        patch.object(ui.backend, "steam_client_version", return_value="1788989629") as steam_version, \
        patch.object(ui.backend, "privileged_request", side_effect=os_request), \
        patch.object(ui.backend, "privileged_command", side_effect=os_command), \
        patch.object(ui.backend, "connection_info", return_value={"addresses": [("wlan0", "192.0.2.44")]}), \
        patch.object(ui.backend, "system_info", return_value={"Device": "AYN Odin 2 Portal", "Kernel": "6.18.0-armada", "Storage": "42.0 GiB free of 128.0 GiB"}), \
        patch.object(ui.backend.Path, "home", return_value=Path(directory)):
    operation_script = Path(directory) / "os-operation"
    operation_script.write_text('#!/bin/sh\necho "70%"\nsleep 0.5\nif [ "$1" = 0 ]; then echo "OS operation completed"; else echo "Download failed"; fi\nexit "$1"\n')
    operation_script.chmod(0o755)
    app = ui.ToolsApplication()
    app.set_flags(ui.Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    app.activate()
    window = app.window
    wait_for(lambda: not window.refreshing and window.get_mapped())
    wait_for(lambda: window.updates.state is not None)
    assert window.steam_version.get_subtitle() == "1788989629"
    assert not window.ssh_switch.get_active()
    assert "Stopped" in window.ssh_row.get_subtitle()
    assert window.connection_row.get_subtitle() == "192.0.2.44"
    window.ssh_switch.set_active(True)
    wait_for(lambda: not window.ssh_busy)
    assert calls[-1] == "enable-ssh"
    assert window.ssh_switch.get_active()
    def resize(width, height):
        window.set_default_size(width, height)
        wait_for(lambda: width - 32 <= window.get_width() <= width and height - 32 <= window.get_height() <= height)
        until = time.monotonic() + 0.2
        wait_for(lambda: time.monotonic() >= until)

    def check_landscape():
        print("Layout", window.get_width(), window.get_height(), flush=True)
        allocations = [section.compute_bounds(window.sections_grid)[1] for section in window.sections]
        assert allocations[0].get_x() == allocations[1].get_x() < allocations[2].get_x() == allocations[3].get_x()
        assert allocations[0].get_y() == allocations[2].get_y()
        assert abs(allocations[1].get_y() - allocations[0].get_y() - allocations[0].get_height() - 16) < 1
        assert abs(allocations[3].get_y() - allocations[2].get_y() - allocations[2].get_height() - 16) < 1
        adjustment = window.scroll.get_vadjustment()
        assert adjustment.get_upper() <= adjustment.get_page_size() + 1, (window.get_width(), window.get_height(), adjustment.get_upper(), adjustment.get_page_size())

    for size in ((1248, 656), (1100, 620), (980, 560)):
        resize(*size)
        check_landscape()
    if screenshot := os.environ.get("ARMADA_TOOLS_SCREENSHOT"):
        until = time.monotonic() + 0.3
        wait_for(lambda: time.monotonic() >= until)
        snapshot = ui.Gtk.Snapshot()
        ui.Gtk.WidgetPaintable.new(window).snapshot(snapshot, window.get_width(), window.get_height())
        texture = window.get_renderer().render_texture(snapshot.to_node(), None)
        assert texture.save_to_png(screenshot)
    window.ssh_switch.set_active(False)
    wait_for(lambda: not window.ssh_busy)
    assert calls[-1] == "disable-ssh"
    assert not state["enabled_at_boot"]

    fail_ssh = True
    window.ssh_switch.set_active(True)
    wait_for(lambda: not window.ssh_busy)
    assert not window.ssh_switch.get_active()
    assert window.ssh_error.get_visible()
    assert window.repair_button.get_sensitive()
    fail_ssh = False
    window.refresh()
    wait_for(lambda: not window.refreshing)

    with patch.object(window.job, "start") as start:
        window.confirm_repair()
        check_confirmation(window.confirmation)
        assert window.confirmation.get_default_response() == "cancel"
        respond(window.confirmation, "cancel")
        wait_for(lambda: window.confirmation is None)
        start.assert_not_called()

    script = Path(directory) / "health-check"
    script.write_text('#!/bin/sh\necho "Verifying factory Steam"\nsleep 0.5\necho "Steam repaired"\n')
    script.chmod(0o755)
    with patch.object(ui.backend, "TOOLS", str(script)):
        window.confirm_repair()
        respond(window.confirmation, "repair")
        assert window.repair_running
        assert not window.repair_button.get_sensitive()
        window.close()
        assert window.get_visible()
        dialog = window.repair_dialog
        assert dialog.heading.get_title() == "Steam Repair"
        assert dialog.get_modal()
        assert dialog.get_transient_for() is window
        assert not dialog.close_button.get_sensitive()
        dialog.close()
        assert dialog.get_visible()
        assert window.job.process.poll() is None
        check_landscape()
        steam_version.return_value = "1788652215"
        wait_for(lambda: not window.repair_running)
        assert window.steam_version.get_subtitle() == "1788652215"
        assert dialog.heading.get_title() == "Steam Repair"
        assert dialog.message.get_text() == "Steam repair complete."
        assert dialog.close_button.get_sensitive()
        assert not dialog.restart_button.get_visible()
        dialog.message.set_text("A long status message " * 1000)
        until = time.monotonic() + 0.2
        wait_for(lambda: time.monotonic() >= until)
        assert dialog.get_height() <= window.get_height(), (dialog.get_width(), dialog.get_height())
        check_landscape()
        dialog.close()
        assert not dialog.get_visible()

    script.write_text('#!/bin/sh\necho "Factory source unavailable"\nexit 1\n')
    with patch.object(ui.backend, "TOOLS", str(script)):
        window.start_repair()
        wait_for(lambda: not window.repair_running)
        assert window.repair_dialog.heading.get_title() == "Steam Repair"
        assert "Factory source unavailable" in window.repair_dialog.message.get_text()
        window.repair_dialog.close()

    with patch.object(window, "start_repair") as start:
        window.repair_button.emit("clicked")
        assert "factory Steam client" in window.confirmation.get_body()
        respond(window.confirmation, "repair")
        start.assert_called_once_with()

    updates = window.updates
    for attribute in ("requesting", "loading"):
        setattr(updates, attribute, True)
        window.close()
        assert window.get_visible()
        setattr(updates, attribute, False)
    updates.render(os_state.copy())
    assert updates.current.get_subtitle() == "20260919.current"
    assert updates.previous.get_subtitle() == "20260907.previous"
    updates.result = "No new image was needed."
    updates.render(os_state.copy())
    assert "No new image" in updates.message.get_text()
    updates.channel.set_selected(2)
    wait_for(lambda: not updates.requesting and not updates.loading)
    assert os_state["channel"] == "preview"
    assert not updates.message.get_visible()
    assert ("channel-preview", ()) in os_calls
    updates.update.emit("clicked")
    wait_for(lambda: updates.confirmation is not None)
    assert "currently selected channel" in updates.confirmation.get_body()
    check_confirmation(updates.confirmation)
    respond(updates.confirmation, "cancel")
    assert not any(call[0] == "update-os" for call in os_calls)
    updates.update.emit("clicked")
    wait_for(lambda: updates.confirmation is not None)
    respond(updates.confirmation, "proceed")
    wait_for(lambda: updates.operation.progress.get_fraction() == 0.7)
    assert updates.requesting
    updates.operation.close()
    assert updates.operation.get_visible()
    assert not updates.operation.close_button.get_sensitive()
    assert not updates.operation.restart_button.get_visible()
    assert not updates.update.get_sensitive()
    assert not updates.channel.get_sensitive()
    assert not window.repair_button.get_sensitive()
    calls_before = len(os_calls)
    updates.request("update-os")
    assert len(os_calls) == calls_before
    window.close()
    assert window.get_visible()
    wait_for(lambda: not updates.loading and not updates.requesting)
    assert updates.operation.get_modal()
    assert "OS operation completed" in updates.operation.message.get_text()
    assert updates.operation.close_button.get_sensitive()
    assert updates.operation.restart_button.get_visible()
    updates.operation.restart_button.emit("clicked")
    assert not updates.operation.get_visible()
    assert updates.confirmation.get_heading() == "Restart Now?"
    respond(updates.confirmation, "cancel")
    assert not any(call[0] == "restart-os" for call in os_calls)
    assert updates.job.log.exists()
    assert updates.message.get_text() == "Update installed. Restart to apply."
    updates.rollback.emit("clicked")
    assert updates.confirmation.get_heading() == "Roll Back Armada?"
    assert "20260907.previous" in updates.confirmation.get_body()
    check_confirmation(updates.confirmation)
    assert "discarded" in updates.confirmation.get_body()
    respond(updates.confirmation, "cancel")
    assert not any(call[0] == "rollback-os" for call in os_calls)
    updates.rollback.emit("clicked")
    respond(updates.confirmation, "proceed")
    wait_for(lambda: not updates.loading and not updates.requesting)
    assert updates.operation.get_modal()
    assert updates.operation.heading.get_title() == "OS Rollback"
    assert updates.operation.close_button.get_sensitive()
    assert updates.operation.restart_button.get_visible()
    updates.operation.restart_button.emit("clicked")
    assert updates.message.get_text() == "Rollback ready. Restart to apply."
    assert updates.update.get_sensitive()
    assert updates.channel.get_sensitive()
    respond(updates.confirmation, "proceed")
    wait_for(lambda: not updates.loading and not updates.requesting)
    assert ("update-os", ()) in os_calls
    assert ("rollback-os", ("b" * 64,)) in os_calls
    assert ("restart-os", ()) in os_calls
    fail_operation = True
    updates.request("update-os")
    wait_for(lambda: not updates.loading and not updates.requesting)
    assert updates.operation.heading.get_title() == "OS Update"
    assert "Download failed" in updates.operation.message.get_text()
    assert not updates.operation.restart_button.get_visible()
    updates.operation.close()
    assert updates.update.get_sensitive()
    assert window.repair_button.get_sensitive()
    fail_operation = False
    updates.result = ""
    os_state["rollback"] = None
    os_state["rollback_queued"] = False
    os_state["reboot_ready"] = False
    updates.refresh()
    wait_for(lambda: not updates.loading)
    assert not updates.rollback.get_sensitive()
    assert "No previous" in updates.previous.get_subtitle()

    custom = os_state.copy()
    custom.update(channel="fast-wifi-reconnect", channels=[])
    updates.render(custom)
    assert updates.channel.get_use_subtitle()
    assert updates.channel.get_subtitle() == "fast-wifi-reconnect"
    assert updates.channel.get_subtitle_lines() == 0
    assert updates.channel.get_sensitive()
    assert not updates.channel.get_activatable()
    assert updates.update.is_sensitive()
    check_landscape()
    updates.render(os_state.copy())
    assert not updates.channel.get_use_subtitle()
    assert not updates.channel.get_subtitle()
    assert updates.channel.get_selected_item().get_string() == os_state["channel"].title()

    resize(400, 620)
    allocations = [section.compute_bounds(window.sections_grid)[1] for section in window.sections]
    assert max(a.get_x() for a in allocations) - min(a.get_x() for a in allocations) < 1, [(a.get_x(), a.get_y()) for a in allocations]
    assert all(allocations[index].get_y() < allocations[index + 1].get_y() for index in range(3))
    adjustment = window.scroll.get_hadjustment()
    assert adjustment.get_upper() <= adjustment.get_page_size() + 1
    resize(980, 560)
    assert window.sections[0].compute_bounds(window.sections_grid)[1].get_x() < window.sections[2].compute_bounds(window.sections_grid)[1].get_x()

    window.close()
    assert not window.get_visible()
print("Native window, manual entry, SSH state/toggle/errors, repair confirmation/results, wait before closing, OS channels/update/rollback/restart, and narrow layout checks passed")
