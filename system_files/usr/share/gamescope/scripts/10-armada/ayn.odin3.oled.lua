-- Qualified AYN Odin 3 fixed-panel HDR profile.
--
-- The internal DSI panel has no KMS EDID.  Armada's Gamescope patch accepts a
-- no-EDID profile only when this exact device, connector, internal-panel flag,
-- Gamma 2.2 output transfer, physical size, colorimetry, and luminance policy
-- are all present.  Steam still owns HDR on/off state at runtime.

local function env_number(name)
    local value = tonumber(os.getenv(name))
    if value == nil or value ~= value or value == math.huge or value == -math.huge then
        return nil
    end
    return value
end

local function valid_xy(x, y)
    return x ~= nil and y ~= nil and x > 0 and x < 1 and y > 0 and y < 1 and x + y <= 1
end

local r_x = env_number("GAMESCOPE_ARMADA_HDR_R_X")
local r_y = env_number("GAMESCOPE_ARMADA_HDR_R_Y")
local g_x = env_number("GAMESCOPE_ARMADA_HDR_G_X")
local g_y = env_number("GAMESCOPE_ARMADA_HDR_G_Y")
local b_x = env_number("GAMESCOPE_ARMADA_HDR_B_X")
local b_y = env_number("GAMESCOPE_ARMADA_HDR_B_Y")
local w_x = env_number("GAMESCOPE_ARMADA_HDR_W_X")
local w_y = env_number("GAMESCOPE_ARMADA_HDR_W_Y")
local max_cll = env_number("GAMESCOPE_ARMADA_HDR_MAX_CLL")
local max_fall = env_number("GAMESCOPE_ARMADA_HDR_MAX_FALL")
local min_cll = env_number("GAMESCOPE_ARMADA_HDR_MIN_CLL")
local sdr_white = env_number("GAMESCOPE_ARMADA_HDR_SDR_WHITE")
local width_mm = env_number("GAMESCOPE_ARMADA_PANEL_NATIVE_WIDTH_MM")
local height_mm = env_number("GAMESCOPE_ARMADA_PANEL_NATIVE_HEIGHT_MM")

local valid = os.getenv("ARMADA_HDR_CAPABLE") == "1"
    and os.getenv("GAMESCOPE_ARMADA_FIXED_PANEL_POLICY") == "ayn-odin-3:DSI-1"
    and os.getenv("GAMESCOPE_ARMADA_HDR_PRODUCTION_MODE") == "immutable-image"
    and os.getenv("GAMESCOPE_ARMADA_HDR_VALIDATED") == "1"
    and os.getenv("GAMESCOPE_INTERNAL_DISPLAY_ID") == "ayn-odin-3"
    and os.getenv("GAMESCOPE_ARMADA_HDR_OUTPUT_EOTF") == "gamma22"
    and valid_xy(r_x, r_y) and valid_xy(g_x, g_y)
    and valid_xy(b_x, b_y) and valid_xy(w_x, w_y)
    and r_x == 0.6800 and r_y == 0.3200
    and g_x == 0.2650 and g_y == 0.6900
    and b_x == 0.1500 and b_y == 0.0600
    and w_x == 0.3127 and w_y == 0.3290
    and max_cll == 650 and max_fall == 650
    and min_cll == 0.0020000000949949
    and sdr_white == 203
    and width_mm == 75 and height_mm == 133

if valid then
    gamescope.config.known_displays.armada_ayn_odin3_oled = {
        pretty_name = "AYN Odin 3 internal OLED (650-nit HDR)",
        allow_no_edid = true,
        physical_size = {
            width_mm = width_mm,
            height_mm = height_mm,
        },
        colorimetry = {
            r = { x = r_x, y = r_y },
            g = { x = g_x, y = g_y },
            b = { x = b_x, y = b_y },
            w = { x = w_x, y = w_y },
        },
        hdr = {
            supported = true,
            eotf = gamescope.eotf.gamma22,
            max_content_light_level = max_cll,
            max_frame_average_luminance = max_fall,
            min_content_light_level = min_cll,
        },
        matches = function(display)
            local connector = display.connector or display.connector_name
            local internal = display.internal == true or display.is_internal == true
            if display.device_id == "ayn-odin-3"
                and connector == "DSI-1"
                and internal
                and display.has_edid == false then
                return 6000
            end
            return -1
        end,
    }
    gamescope.log(
        gamescope.log_priority.info,
        "Registered qualified AYN Odin 3 internal OLED HDR profile (650 nits)"
    )
else
    gamescope.log(
        gamescope.log_priority.info,
        "AYN Odin 3 internal OLED HDR profile remains disabled: production policy incomplete"
    )
end
