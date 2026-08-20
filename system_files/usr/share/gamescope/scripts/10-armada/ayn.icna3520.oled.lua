-- ICNA3520 OLED used by the AYN Odin 3 and Thor top displays. It exposes no EDID,
-- so gamescope synthesizes one and identifies the display through
-- GAMESCOPE_INTERNAL_DEVICE_ID; this profile supplies the panel's
-- colorimetry and HDR capability. Refresh rates come from the kernel
-- mode list. Steam owns HDR behavior at runtime.
gamescope.config.known_displays.armada_ayn_icna3520_oled = {
    pretty_name = "AYN ICNA3520 internal OLED",
    colorimetry = {
        r = { x = 0.6800, y = 0.3200 },
        g = { x = 0.2650, y = 0.6900 },
        b = { x = 0.1500, y = 0.0600 },
        w = { x = 0.3127, y = 0.3290 },
    },
    hdr = {
        supported = true,
        eotf = gamescope.eotf.gamma22,
        max_content_light_level = 650,
        max_frame_average_luminance = 650,
        min_content_light_level = 0.002,
    },
    matches = function(display)
        if (display.device_id == "ayn-odin-3" or display.device_id == "ayn-thor")
            and display.internal and not display.has_edid then
            return 6000
        end
        return -1
    end,
}
