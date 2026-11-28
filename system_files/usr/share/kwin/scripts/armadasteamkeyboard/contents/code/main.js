// Steam places its keyboard above the panel; it is kept above, so docking it lower covers the panel.
function isSteamKeyboard(window) {
    return window.resourceClass == "steam" && window.utility && window.skipTaskbar;
}

function dock(window) {
    const area = workspace.clientArea(KWin.FullScreenArea, window);
    const frame = window.frameGeometry;
    const x = area.x + Math.round((area.width - frame.width) / 2);
    const y = area.y + area.height - frame.height;
    if (frame.x != x || frame.y != y) {
        window.frameGeometry = { x: x, y: y, width: frame.width, height: frame.height };
    }
}

function track(window) {
    if (!isSteamKeyboard(window)) {
        return;
    }
    dock(window);
    window.frameGeometryChanged.connect(() => dock(window));
}

workspace.windowList().forEach(track);
workspace.windowAdded.connect(track);

// Clicking a key would focus the keyboard itself, taking text focus away from the field being typed into.
let typingWindow = workspace.activeWindow;
workspace.windowActivated.connect((window) => {
    if (window && isSteamKeyboard(window)) {
        if (typingWindow && !typingWindow.deleted) {
            workspace.activeWindow = typingWindow;
        }
        return;
    }
    typingWindow = window;
});
