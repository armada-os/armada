#ifndef ARMADA_AUTOHDR_H
#define ARMADA_AUTOHDR_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
# if defined(ARMADA_AUTOHDR_BUILDING_LIBRARY)
#  define ARMADA_AUTOHDR_API __declspec(dllexport)
# else
#  define ARMADA_AUTOHDR_API __declspec(dllimport)
# endif
#else
# define ARMADA_AUTOHDR_API __attribute__((visibility("default")))
#endif

#define ARMADA_AUTOHDR_ABI_VERSION 1

#ifdef __cplusplus
extern "C" {
#endif

typedef struct armada_autohdr_rgb {
    float r, g, b;
} armada_autohdr_rgb;

typedef struct armada_autohdr_transform {
    /* Column-major matrix from output RGB to native panel RGB. */
    float native_from_output[9];
    float sdr_nits;
    float target_nits;
} armada_autohdr_transform;

typedef struct armada_autohdr_capabilities {
    uint32_t color_management;
    uint32_t hdr;
    uint32_t lease_client;
    uint32_t legacy_itm;
    uint32_t override_luts;
    uint32_t hardware_luts;
    uint32_t peak_nits;
} armada_autohdr_capabilities;

typedef struct armada_autohdr_content {
    uint32_t game;
    uint32_t hdr;
    uint32_t steam_focused;
} armada_autohdr_content;

/* Initialize states to zero before their first use. */
typedef struct armada_autohdr_state {
    uint32_t requested;
    uint32_t luts_enabled;
    uint32_t presented;
} armada_autohdr_state;

typedef struct armada_autohdr_scanout_state {
    uint64_t preferred_pipeline;
} armada_autohdr_scanout_state;

/* Callbacks and their context are borrowed for this synchronous call. */
typedef struct armada_autohdr_scanout_ops {
    void *data;
    size_t pipeline_count;
    size_t layer_count;
    uint64_t (*pipeline)(void *data, size_t index);
    void (*unset_pipeline)(void *data, size_t layer);
    void (*set_pipeline)(void *data, size_t layer, uint64_t pipeline);
    int (*apply)(void *data);
    uint32_t (*needs_composition)(void *data);
} armada_autohdr_scanout_ops;

ARMADA_AUTOHDR_API uint32_t armada_autohdr_abi_version(void);
ARMADA_AUTOHDR_API float armada_autohdr_inverse_tone_map(float value, float sdr_nits, float target_nits);
ARMADA_AUTOHDR_API armada_autohdr_rgb armada_autohdr_apply_transform(
    const armada_autohdr_transform *transform, armada_autohdr_rgb color);
ARMADA_AUTOHDR_API uint32_t armada_autohdr_available(
    uint32_t enabled, const armada_autohdr_capabilities *capabilities);
ARMADA_AUTOHDR_API uint32_t armada_autohdr_active(
    uint32_t available, const armada_autohdr_content *content);
ARMADA_AUTOHDR_API uint32_t armada_autohdr_reconcile(armada_autohdr_state *state, uint32_t requested);
ARMADA_AUTOHDR_API void armada_autohdr_luts_updated(armada_autohdr_state *state);
ARMADA_AUTOHDR_API uint32_t armada_autohdr_prepare(
    uint32_t active, uint32_t fading, uint32_t has_layers, uint32_t has_luts, uint32_t hdr);
ARMADA_AUTOHDR_API void armada_autohdr_presented(
    armada_autohdr_state *state, uint32_t primary, uint32_t success, uint32_t converted);
ARMADA_AUTOHDR_API uint32_t armada_autohdr_hdr_presented(const armada_autohdr_state *state);
ARMADA_AUTOHDR_API int armada_autohdr_scanout_apply(
    armada_autohdr_scanout_state *state, uint32_t game_layer_mask, const armada_autohdr_scanout_ops *ops);

#ifdef __cplusplus
}
#endif

#endif
