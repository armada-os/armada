-- Keep the hidden physical speaker route at unity. User-facing volume belongs
-- to the Stereo and Virtual Surround Sound sinks that feed this route.

local cutils = require ("common-utils")
local log = Log.open_topic ("odin3-speaker-route-unity")

local target_device = "alsa_card.platform-sound"
local target_route = "[Out] Speaker"
local epsilon = 0.000001

local function enforce (device)
  if not device or device.properties["device.name"] ~= target_device then
    return
  end

  for param in device:iterate_params ("Route") do
    local route = cutils.parseParam (param, "Route")
    if route and route.name == target_route and route.direction == "Output" then
      local props = route.props and route.props.properties
      local current = props and props.channelVolumes
      local needs_fix = (not props) or (props.mute ~= false)

      if type (current) ~= "table" or #current == 0 then
        needs_fix = true
      else
        for _, volume in ipairs (current) do
          if type (volume) ~= "number"
              or math.abs (volume - 1.0) > epsilon then
            needs_fix = true
            break
          end
        end
      end

      if not needs_fix then
        return
      end

      local unity = { "Spa:Float" }
      local channels =
          (type (current) == "table" and #current > 0) and #current or 2
      for _ = 1, channels do
        unity[#unity + 1] = 1.0
      end

      local route_props = Pod.Object {
        "Spa:Pod:Object:Param:Props",
        "Props",
        mute = false,
        channelVolumes = Pod.Array (unity),
      }
      local fixed_route = Pod.Object {
        "Spa:Pod:Object:Param:Route",
        "Route",
        index = route.index,
        device = route.device,
        props = route_props,
        save = true,
      }

      log:info (device, "restoring [Out] Speaker route to unity and unmuted")
      device:set_param ("Route", fixed_route)
      return
    end
  end
end

SimpleEventHook {
  name = "odin3-audio/keep-speaker-route-unity",
  after = {
    "device/select-route",
    "device/store-or-restore-routes",
  },
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "device-added" },
    },
    EventInterest {
      Constraint { "event.type", "=", "device-params-changed" },
      Constraint { "event.subject.param-id", "=", "Route" },
    },
  },
  execute = function (event)
    enforce (event:get_subject ())
  end,
}:register ()
