#include "armada-autohdr.h"

#include <algorithm>
#include <cerrno>
#include <cmath>

uint32_t armada_autohdr_abi_version(void)
{
    return ARMADA_AUTOHDR_ABI_VERSION;
}

float armada_autohdr_inverse_tone_map(float value, float sdr_nits, float target_nits)
{
    if (!(value > 0.0f && sdr_nits > 0.0f && target_nits > 0.0f))
        return 0.0f;

    // Expand highlights with the neutral BT.2446 A curve.
    constexpr float inverse_gamma = 2.4f;
    constexpr float gamma = 1.0f / inverse_gamma;
    const float y_sdr = std::pow(std::max(0.0f, std::min(1.0f, value)), gamma);
    const float p_sdr = 1.0f + 32.0f * std::pow(sdr_nits / 10000.0f, gamma);
    const float y_c = std::log(y_sdr * (p_sdr - 1.0f) + 1.0f) / std::log(p_sdr);
    const float y_p0 = y_c / 1.0770f;
    const float y_p1 = (-2.7811f + std::sqrt(4.83307641f - 4.604f * y_c)) / -2.302f;
    const float y_p2 = (y_c - 0.5000f) / 0.5000f;
    // Rounded segment endpoints must not make the curve decrease.
    const float y_p = y_p0 <= 0.7399f ? y_p0 : y_p1 < 0.9909f ?
        std::max(y_p1, 0.7399f) : std::max(y_p2, 0.9909f);
    const float p_hdr = 1.0f + 32.0f * std::pow(target_nits / 10000.0f, gamma);
    const float y = (std::pow(p_hdr, y_p) - 1.0f) / (p_hdr - 1.0f);
    return std::pow(y, inverse_gamma);
}

armada_autohdr_rgb armada_autohdr_apply_transform(
    const armada_autohdr_transform *transform, armada_autohdr_rgb color)
{
    const float *matrix = transform->native_from_output;
    // Measure the peak in the panel gamut, including for BT.2020 output.
    const armada_autohdr_rgb native{
        matrix[0] * color.r + matrix[3] * color.g + matrix[6] * color.b,
        matrix[1] * color.r + matrix[4] * color.g + matrix[7] * color.b,
        matrix[2] * color.r + matrix[5] * color.g + matrix[8] * color.b,
    };
    const float maximum = std::max({native.r, native.g, native.b});
    if (!(maximum > 0.0f && transform->target_nits > 0.0f))
        return {0.0f, 0.0f, 0.0f};

    // One RGB gain preserves the SDR channel ratios.
    const float mapped = armada_autohdr_inverse_tone_map(maximum / transform->target_nits,
        transform->sdr_nits, transform->target_nits) * transform->target_nits;
    const float gain = std::min(mapped, transform->target_nits) / maximum;
    return {color.r * gain, color.g * gain, color.b * gain};
}

uint32_t armada_autohdr_available(uint32_t enabled, const armada_autohdr_capabilities *caps)
{
    return enabled && caps->color_management && caps->hdr && !caps->lease_client &&
        !caps->legacy_itm && !caps->override_luts && caps->hardware_luts && caps->peak_nits > 0;
}

uint32_t armada_autohdr_active(uint32_t available, const armada_autohdr_content *content)
{
    // A separate Steam overlay must not change the held game's mapping.
    return available && content->game && !content->hdr && !content->steam_focused;
}

uint32_t armada_autohdr_reconcile(armada_autohdr_state *state, uint32_t requested)
{
    state->requested = requested != 0;
    return state->requested != state->luts_enabled;
}

void armada_autohdr_luts_updated(armada_autohdr_state *state)
{
    state->luts_enabled = state->requested;
}

uint32_t armada_autohdr_prepare(
    uint32_t active, uint32_t fading, uint32_t has_layers, uint32_t has_luts, uint32_t hdr)
{
    return active && !fading && has_layers && has_luts && !hdr;
}

void armada_autohdr_presented(
    armada_autohdr_state *state, uint32_t primary, uint32_t success, uint32_t converted)
{
    if (primary)
        state->presented = success && converted;
}

uint32_t armada_autohdr_hdr_presented(const armada_autohdr_state *state)
{
    return state->presented;
}

int armada_autohdr_scanout_apply(
    armada_autohdr_scanout_state *state, uint32_t game_layer_mask, const armada_autohdr_scanout_ops *ops)
{
    if (ops->layer_count > 32)
        return -EINVAL;

    // Drop the game's constraint from SDR overlays and unused layer slots.
    for (size_t i = 0; i < ops->layer_count; ++i)
        if (!(game_layer_mask & (uint32_t(1) << i)))
            ops->unset_pipeline(ops->data, i);

    if (!game_layer_mask)
        return ops->apply(ops->data);

    auto find_pipeline = [&](uint64_t pipeline, size_t end)
    {
        for (size_t i = 0; i < end; ++i)
            if (ops->pipeline(ops->data, i) == pipeline)
                return true;
        return false;
    };
    // Do not retry a pipeline that disappeared from the current plane list.
    if (!find_pipeline(state->preferred_pipeline, ops->pipeline_count))
        state->preferred_pipeline = 0;

    auto try_pipeline = [&](uint64_t pipeline)
    {
        for (size_t i = 0; i < ops->layer_count; ++i)
            if (game_layer_mask & (uint32_t(1) << i))
                ops->set_pipeline(ops->data, i, pipeline);

        int ret = ops->apply(ops->data);
        if (ret == 0)
        {
            if (!ops->needs_composition(ops->data))
            {
                state->preferred_pipeline = pipeline;
                return 0;
            }
            ret = -EINVAL;
        }
        if (pipeline == state->preferred_pipeline)
            state->preferred_pipeline = 0;
        return ret;
    };

    // Try the last working pipeline before other layouts, without allocating.
    const uint64_t preferred = state->preferred_pipeline;
    bool tried_pipeline = preferred != 0;
    int ret = preferred ? try_pipeline(preferred) : -EINVAL;
    if (tried_pipeline && ret != -EINVAL)
        return ret;

    for (size_t i = 0; i < ops->pipeline_count; ++i)
    {
        const uint64_t pipeline = ops->pipeline(ops->data, i);
        if (!pipeline || pipeline == preferred || find_pipeline(pipeline, i))
            continue;
        tried_pipeline = true;
        ret = try_pipeline(pipeline);
        if (ret != -EINVAL)
            return ret;
    }
    return tried_pipeline ? ret : ops->apply(ops->data);
}
