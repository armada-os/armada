-- ICNA3512 OLED on the AYANEO Pocket DS top display. Split from the shared
-- ICNA3512 profile because this panel is HDR capable; luminance values are
-- what Android reports for it. Steam owns HDR behavior at runtime.
gamescope.config.known_displays.armada_ayaneo_pocket_ds_oled = {
    pretty_name = "AYANEO Pocket DS internal OLED",
    colorimetry = {
        r = { x = 0.6800, y = 0.3200 },
        g = { x = 0.2650, y = 0.6900 },
        b = { x = 0.1500, y = 0.0600 },
        w = { x = 0.3127, y = 0.3290 },
    },
    hdr = {
        supported = true,
        eotf = gamescope.eotf.gamma22,
        max_content_light_level = 786,
        max_frame_average_luminance = 393,
        min_content_light_level = 0,
    },
    matches = function(display)
        if display.device_id == "ayaneo-pocket-ds"
            and display.internal and not display.has_edid then
            return 6000
        end
        return -1
    end,
}
