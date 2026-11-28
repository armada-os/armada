#ifndef GAMESCOPE_COLOR_PROVIDER_H
#define GAMESCOPE_COLOR_PROVIDER_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
# if defined(GAMESCOPE_COLOR_PROVIDER_BUILDING_LIBRARY)
#  define GAMESCOPE_COLOR_PROVIDER_API __declspec(dllexport)
# else
#  define GAMESCOPE_COLOR_PROVIDER_API __declspec(dllimport)
# endif
#else
# define GAMESCOPE_COLOR_PROVIDER_API __attribute__((visibility("default")))
#endif

#define GAMESCOPE_COLOR_PROVIDER_ABI 1

#ifdef __cplusplus
extern "C" {
#endif

typedef struct gamescope_color_rgb {
    float r, g, b;
} gamescope_color_rgb;

typedef struct gamescope_color_capabilities {
    uint32_t color_management;
    uint32_t hdr;
    uint32_t lease_client;
    uint32_t legacy_itm;
    uint32_t override_luts;
    uint32_t hardware_luts;
    uint32_t peak_nits;
} gamescope_color_capabilities;

typedef struct gamescope_color_content {
    uint32_t game;
    uint32_t hdr;
    uint32_t steam_focused;
} gamescope_color_content;

typedef struct gamescope_color_config {
    /* Column-major matrix from output RGB to native panel RGB. */
    float native_from_output[9];
    float sdr_nits;
    float target_nits;
    float input_gain;
} gamescope_color_config;

typedef struct gamescope_color_plan {
    float input_gain;
    float g22_luminance;
    gamescope_color_rgb (*map)(gamescope_color_rgb color, const void *data);
    /* Borrowed until the next configure call on this instance. */
    const void *data;
} gamescope_color_plan;

typedef struct gamescope_color_frame {
    uint32_t enabled;
    uint32_t active;
    uint32_t fading;
    uint32_t has_layers;
    uint32_t has_luts;
    uint32_t hdr;
    uint32_t primary;
    uint32_t has_connector;
} gamescope_color_frame;

/* Callbacks and their context are borrowed for the synchronous call. */
typedef struct gamescope_color_present_ops {
    void *data;
    void (*attach_game_luts)(void *data);
    int (*present)(void *data);
} gamescope_color_present_ops;

typedef struct gamescope_color_present_result {
    int status;
    uint32_t hdr_presented;
} gamescope_color_present_result;

typedef struct gamescope_color_scanout_ops {
    void *data;
    size_t pipeline_count;
    size_t layer_count;
    uint64_t (*pipeline)(void *data, size_t index);
    void (*unset_pipeline)(void *data, size_t layer);
    void (*set_pipeline)(void *data, size_t layer, uint64_t pipeline);
    int (*apply)(void *data);
    uint32_t (*needs_composition)(void *data);
} gamescope_color_scanout_ops;

typedef struct gamescope_color_provider {
    uint32_t abi_version;
    uint32_t struct_size;
    void *(*create)(void);
    void (*destroy)(void *instance);
    uint32_t (*available)(const gamescope_color_capabilities *capabilities);
    uint32_t (*active)(uint32_t available, const gamescope_color_content *content);
    gamescope_color_plan (*configure)(void *instance, const gamescope_color_config *config);
    gamescope_color_present_result (*present)(void *instance,
        const gamescope_color_frame *frame, const gamescope_color_present_ops *ops);
    int (*scanout)(void *instance, uint32_t game_layer_mask, const gamescope_color_scanout_ops *ops);
} gamescope_color_provider;

static inline uint32_t gamescope_color_provider_is_compatible(const gamescope_color_provider *provider)
{
    return provider && provider->abi_version == GAMESCOPE_COLOR_PROVIDER_ABI &&
        provider->struct_size >= sizeof(gamescope_color_provider) &&
        provider->create && provider->destroy && provider->available && provider->active &&
        provider->configure && provider->present && provider->scanout;
}

typedef const gamescope_color_provider *(*gamescope_color_provider_get_interface_fn)(uint32_t abi_version);

GAMESCOPE_COLOR_PROVIDER_API const gamescope_color_provider *gamescope_color_provider_get_interface(uint32_t abi_version);

#ifdef __cplusplus
}
#endif

#endif
