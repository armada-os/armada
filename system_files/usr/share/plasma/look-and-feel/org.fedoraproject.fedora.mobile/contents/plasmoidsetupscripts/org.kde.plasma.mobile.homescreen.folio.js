// Add return to gamemode to the homescreen
applet.writeConfig("Pages", `[[
    {"column": 0, "row": 0, "storageId": "armada-return-to-gamemode.desktop", "type": "application"}
]]`);

// Add some useful apps that we ship to the favourites section
applet.writeConfig("Favourites", `[
    {"storageId": "org.mozilla.firefox.desktop", "type": "application"},
    {"storageId": "io.github.kolunmi.Bazaar.desktop", "type": "application"},
    {"storageId": "org.kde.dolphin.desktop", "type": "application"},
    {"storageId": "steam.desktop", "type": "application"}
]`);

applet.reloadConfig();
