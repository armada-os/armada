-- Keep the qualified fixed-panel policy deterministic.  This affects only the
-- immutable Odin 3 production session; every other device retains Gamescope's
-- normal local/user script behavior.
if os.getenv("ARMADA_HDR_CAPABLE") == "1"
    and os.getenv("GAMESCOPE_ARMADA_FIXED_PANEL_POLICY") == "ayn-odin-3:DSI-1"
    and os.getenv("GAMESCOPE_ARMADA_HDR_PRODUCTION_MODE") == "immutable-image"
    and os.getenv("GAMESCOPE_ARMADA_HDR_VALIDATED") == "1" then
    gamescope.convars.script_use_local_scripts.value = false
    gamescope.convars.script_use_user_scripts.value = false
    gamescope.log(
        gamescope.log_priority.info,
        "Armada Odin 3 HDR production policy disabled local and user Gamescope scripts"
    )
end
