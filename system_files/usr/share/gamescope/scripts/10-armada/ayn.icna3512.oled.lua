-- ICNA3512 OLED used by the AYN Odin 2 Portal main display. Same DDIC family as
-- ICNA3520 (Odin 3/Thor) but an incompatible revision (vendor MIPI commands
-- differ), so it gets its own known_displays entry. It exposes no EDID, so
-- gamescope synthesizes one and identifies the display through
-- GAMESCOPE_INTERNAL_DEVICE_ID. Colorimetry uses Display-P3 primaries,
-- confirmed (not guessed) from the panel's own vendor QDCM calibration data
-- (qdcm_calib_data_icna3512_amoled_panel_with_DSC.json on-device: HDR profile
-- Applicability.ColorPrimaries = "P3", WhitePoint = 6500), matching Android's
-- active DISPLAY_P3 color mode for this panel. Android's own HdrCapabilities
-- reports lower light levels (peak 420 / avg 210.16 / min 0.323 nits) than
-- the spec-sheet 800 used below; kept at 800 for now, real values may
-- replace it later. Steam owns HDR behavior at runtime.
gamescope.config.known_displays.armada_ayn_icna3512_oled = {
    pretty_name = "AYN ICNA3512 internal OLED",
    colorimetry = {
        r = { x = 0.6800, y = 0.3200 },
        g = { x = 0.2650, y = 0.6900 },
        b = { x = 0.1500, y = 0.0600 },
        w = { x = 0.3127, y = 0.3290 },
    },
    hdr = {
        supported = true,
        eotf = gamescope.eotf.gamma22,
        max_content_light_level = 800,
        max_frame_average_luminance = 800,
        min_content_light_level = 0.002,
    },
    matches = function(display)
        if display.device_id == "ayn-odin-2-portal"
            and display.internal and not display.has_edid then
            return 6000
        end
        return -1
    end,
}
