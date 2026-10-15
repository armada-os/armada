-- ICNA3512 OLED used by the AYN Odin 2 Portal, AYANEO Pocket EVO, and Pocket DS
-- top display. It exposes no EDID, so gamescope synthesizes one and identifies
-- the display through GAMESCOPE_INTERNAL_DEVICE_ID; this profile supplies the
-- panel's colorimetry (nominal DCI-P3, not measured) and HDR capability.
-- Steam owns HDR behavior at runtime.
gamescope.config.known_displays.armada_ayn_icna3512_oled = {
    pretty_name = "ICNA3512 internal OLED",
    colorimetry = {
        r = { x = 0.6800, y = 0.3200 },
        g = { x = 0.2650, y = 0.6900 },
        b = { x = 0.1500, y = 0.0600 },
        w = { x = 0.3127, y = 0.3290 },
    },
    hdr = {
        supported = true,
        eotf = gamescope.eotf.gamma22,
        max_content_light_level = 780,
        max_frame_average_luminance = 390,
        min_content_light_level = 0,
    },
    matches = function(display)
        if (display.device_id == "ayn-odin-2-portal"
            or display.device_id == "ayaneo-pocket-evo"
            or display.device_id == "ayaneo-pocket-ds")
            and display.internal and not display.has_edid then
            return 6000
        end
        return -1
    end,
}
