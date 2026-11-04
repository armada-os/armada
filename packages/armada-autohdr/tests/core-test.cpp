#include "gamescope-color-provider.h"

#include <algorithm>
#include <array>
#include <bit>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>

static unsigned checks = 0;

#define CHECK(condition) do { \
    ++checks; \
    if (!(condition)) { \
        std::fprintf(stderr, "Check failed at line %d: %s\n", __LINE__, #condition); \
        std::exit(1); \
    } \
} while (false)

static const gamescope_color_provider &api()
{
    return *gamescope_color_provider_get_interface(GAMESCOPE_COLOR_PROVIDER_ABI);
}

struct Context
{
    void *instance = api().create();
    Context() { CHECK(instance); }
    ~Context() { api().destroy(instance); }
    Context(const Context &) = delete;
    Context &operator=(const Context &) = delete;
};

static float curve(void *context, float input, float sdr, float peak)
{
    const gamescope_color_config config{{1, 0, 0, 0, 1, 0, 0, 0, 1}, sdr, peak, 1};
    const auto plan = api().configure(context, &config);
    const float value = input * peak;
    const auto mapped = plan.map({value, value, value}, plan.data);
    return peak > 0 ? mapped.r / peak : mapped.r;
}

static void check_interface()
{
    CHECK(!gamescope_color_provider_get_interface(0));
    CHECK(!gamescope_color_provider_get_interface(GAMESCOPE_COLOR_PROVIDER_ABI + 1));
    CHECK(!gamescope_color_provider_is_compatible(nullptr));
    const auto *provider = gamescope_color_provider_get_interface(GAMESCOPE_COLOR_PROVIDER_ABI);
    CHECK(gamescope_color_provider_is_compatible(provider));
    auto table = *provider;
    ++table.abi_version;
    CHECK(!gamescope_color_provider_is_compatible(&table));
    table = *provider;
    --table.struct_size;
    CHECK(!gamescope_color_provider_is_compatible(&table));
    table.struct_size = sizeof(table) + sizeof(void *);
    CHECK(gamescope_color_provider_is_compatible(&table));
    for (auto invalidate : {
        +[](gamescope_color_provider &p) { p.create = nullptr; },
        +[](gamescope_color_provider &p) { p.destroy = nullptr; },
        +[](gamescope_color_provider &p) { p.available = nullptr; },
        +[](gamescope_color_provider &p) { p.active = nullptr; },
        +[](gamescope_color_provider &p) { p.configure = nullptr; },
        +[](gamescope_color_provider &p) { p.present = nullptr; },
        +[](gamescope_color_provider &p) { p.scanout = nullptr; },
    })
    {
        table = *provider;
        invalidate(table);
        CHECK(!gamescope_color_provider_is_compatible(&table));
    }
}

static bool finite(float value)
{
    return (std::bit_cast<uint32_t>(value) & 0x7f800000u) != 0x7f800000u;
}

static double reference_curve(double input, double sdr, double peak)
{
    // Invert the forward curve numerically instead of copying the implementation.
    const double p_sdr = 1.0 + 32.0 * std::pow(sdr / 10000.0, 1.0 / 2.4);
    const double yc = std::log1p(std::pow(std::clamp(input, 0.0, 1.0), 1.0 / 2.4) * (p_sdr - 1.0)) / std::log(p_sdr);
    double low = 0.0, high = 1.0;
    for (unsigned i = 0; i < 60; ++i)
    {
        const double yp = (low + high) * 0.5;
        const double mapped = yp <= 0.7399 ? 1.077 * yp : yp < 0.9909 ?
            (-1.151 * yp + 2.7811) * yp - 0.6302 : 0.5 * yp + 0.5;
        if (mapped < yc)
            low = yp;
        else
            high = yp;
    }
    const double p_hdr = 1.0 + 32.0 * std::pow(peak / 10000.0, 1.0 / 2.4);
    return std::pow(std::expm1((low + high) * 0.5 * std::log(p_hdr)) / (p_hdr - 1.0), 2.4);
}

static bool close(float value, double expected, double margin = 0.0000001, double relative = 0.0005)
{
    return std::fabs(value - expected) <= margin + std::fabs(expected) * relative;
}

static void check_math()
{
    Context context;
    const std::array gaps{
        std::array{1.077 * 0.7399, (-1.151 * 0.7399 + 2.7811) * 0.7399 - 0.6302},
        std::array{(-1.151 * 0.9909 + 2.7811) * 0.9909 - 0.6302, 0.5 * 0.9909 + 0.5},
    };
    for (float sdr : {1.0f, 100.0f, 1000.0f})
        for (float peak : {1.0f, 100.0f, 1000.0f})
        {
            float previous = 0.0f;
            for (unsigned i = 0; i <= 4096; ++i)
            {
                const float input = float(i) / 4096.0f;
                const float value = curve(context.instance, input, sdr, peak);
                CHECK(finite(value));
                CHECK(value + 4.0f * std::numeric_limits<float>::epsilon() >= previous);
                CHECK(value >= 0.0f && value <= 1.00001f);
                CHECK(close(value, reference_curve(input, sdr, peak)));
                previous = value;
            }
            CHECK(std::fabs(previous - 1.0f) < 0.00001f);
            CHECK(curve(context.instance, 2.0f, sdr, peak) == previous);
            const double p_sdr = 1.0 + 32.0 * std::pow(double(sdr) / 10000.0, 1.0 / 2.4);
            for (const auto &gap : gaps)
            {
                float previous_join = 0.0f;
                for (double position : {-0.1, 0.0, 0.25, 0.5, 0.75, 1.0, 1.1})
                {
                    const double yc = gap[0] + position * (gap[1] - gap[0]);
                    const float input = std::pow(std::expm1(yc * std::log(p_sdr)) / (p_sdr - 1.0), 2.4);
                    const float value = curve(context.instance, input, sdr, peak);
                    CHECK(value + 4.0f * std::numeric_limits<float>::epsilon() >= previous_join);
                    CHECK(close(value, reference_curve(input, sdr, peak), 0.000001, 0.000002));
                    previous_join = value;
                }
            }
        }
    CHECK(curve(context.instance, -1.0f, 100.0f, 1000.0f) == 0.0f);
    CHECK(curve(context.instance, 1.0f, 0.0f, 1000.0f) == 0.0f);
    CHECK(curve(context.instance, 1.0f, 100.0f, 0.0f) == 0.0f);

    const std::array matrices{
        std::array{1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f},
        std::array{1.2f, -0.1f, 0.0f, 0.2f, 1.0f, -0.1f, -0.1f, 0.3f, 0.9f},
    };
    for (const auto &matrix : matrices)
        for (float sdr : {1.0f, 100.0f, 1000.0f})
            for (float peak : {1.0f, 100.0f, 1000.0f})
            {
                gamescope_color_config config{{}, sdr, peak, 0.5f};
                std::copy(matrix.begin(), matrix.end(), config.native_from_output);
                const auto plan = api().configure(context.instance, &config);
                CHECK(plan.input_gain == config.input_gain && plan.g22_luminance == peak);
                for (int r = -1; r <= 4; ++r)
                    for (unsigned g = 0; g <= 4; ++g)
                        for (unsigned b = 0; b <= 4; ++b)
                        {
                            const gamescope_color_rgb input{r * peak / 4.0f, g * peak / 4.0f, b * peak / 4.0f};
                            const auto output = plan.map(input, plan.data);
                            CHECK(finite(output.r) && finite(output.g) && finite(output.b));
                            const float native_peak = std::max({matrix[0] * input.r + matrix[3] * input.g + matrix[6] * input.b,
                                matrix[1] * input.r + matrix[4] * input.g + matrix[7] * input.b,
                                matrix[2] * input.r + matrix[5] * input.g + matrix[8] * input.b});
                            const double gain = native_peak > 0.0f ? reference_curve(native_peak / peak, sdr, peak) * peak / native_peak : 0.0;
                            CHECK(close(output.r, input.r * gain, peak * 0.000003));
                            CHECK(close(output.g, input.g * gain, peak * 0.000003));
                            CHECK(close(output.b, input.b * gain, peak * 0.000003));
                            const float native_r = matrix[0] * output.r + matrix[3] * output.g + matrix[6] * output.b;
                            const float native_g = matrix[1] * output.r + matrix[4] * output.g + matrix[7] * output.b;
                            const float native_b = matrix[2] * output.r + matrix[5] * output.g + matrix[8] * output.b;
                            CHECK(std::max({native_r, native_g, native_b}) <= peak + peak * 0.000001f);
                        }
            }
}

static void check_policy()
{
    for (unsigned bits = 0; bits < 128; ++bits)
    {
        const auto flag = [bits](unsigned index) { return uint32_t((bits >> index) & 1); };
        const gamescope_color_capabilities caps{
            flag(0), flag(1), flag(2), flag(3), flag(4), flag(5), flag(6) * 1000,
        };
        const bool expected = (bits & 0x63) == 0x63 && (bits & 0x1c) == 0;
        CHECK(bool(api().available(&caps)) == expected);
    }
    for (unsigned bits = 0; bits < 16; ++bits)
    {
        const gamescope_color_content content{bits & 1u, bits & 2u, bits & 4u};
        CHECK(bool(api().active(bits & 8u, &content)) == (bits == 9));
    }
}

struct PresentFixture
{
    void *instance;
    int status;
    unsigned attached = 0, calls = 0;
    uint32_t observed = 0;

    gamescope_color_present_ops ops()
    {
        return {
            this,
            [](void *data) { ++static_cast<PresentFixture *>(data)->attached; },
            [](void *data) {
                auto &self = *static_cast<PresentFixture *>(data);
                const gamescope_color_frame secondary{};
                const gamescope_color_present_ops probe{nullptr, nullptr, [](void *) { return 0; }};
                self.observed = api().present(self.instance, &secondary, &probe).hdr_presented;
                ++self.calls;
                return self.status;
            },
        };
    }
};

static void check_present()
{
    const gamescope_color_frame seed{1, 1, 0, 1, 1, 0, 1, 1};
    for (uint32_t initial : {0u, 1u})
        for (unsigned bits = 0; bits < 256; ++bits)
            for (int status : {0, -EINVAL})
            {
                Context context;
                PresentFixture fixture{context.instance, 0};
                const auto ops = fixture.ops();
                if (initial)
                    CHECK(api().present(context.instance, &seed, &ops).hdr_presented);
                fixture = {context.instance, status};
                const auto flag = [bits](unsigned bit) { return uint32_t((bits >> bit) & 1); };
                const gamescope_color_frame frame{flag(0), flag(1), flag(2), flag(3), flag(4), flag(5), flag(6), flag(7)};
                const auto result = api().present(context.instance, &frame, &ops);
                const bool converted = (bits & 0x3f) == 0x1b;
                const uint32_t before = !frame.enabled && frame.primary ? 0 : initial;
                const uint32_t after = frame.primary ? frame.enabled && frame.has_connector && status == 0 && converted : initial;
                CHECK(fixture.attached == unsigned(converted) && fixture.calls == 1);
                CHECK(fixture.observed == before);
                CHECK(result.status == status && result.hdr_presented == after);
            }
}

struct ScanoutFixture
{
    std::array<uint64_t, 8> pipelines{};
    std::array<uint64_t, 32> layers{};
    std::array<uint64_t, 8> applied{};
    std::array<int, 8> results{};
    std::array<uint32_t, 8> composition{};
    size_t pipeline_count = 0;
    size_t layer_count = 4;
    unsigned applies = 0;
    unsigned pipeline_reads = 0;
    unsigned unsets = 0;
    unsigned sets = 0;
    uint32_t game_mask = 1;

    gamescope_color_scanout_ops ops()
    {
        return {
            this, pipeline_count, layer_count,
            [](void *data, size_t index) {
                auto &self = *static_cast<ScanoutFixture *>(data);
                ++self.pipeline_reads;
                return self.pipelines.at(index);
            },
            [](void *data, size_t index) {
                auto &self = *static_cast<ScanoutFixture *>(data);
                ++self.unsets;
                self.layers.at(index) = 0;
            },
            [](void *data, size_t index, uint64_t pipeline) {
                auto &self = *static_cast<ScanoutFixture *>(data);
                ++self.sets;
                self.layers.at(index) = pipeline;
            },
            [](void *data) {
                auto &self = *static_cast<ScanoutFixture *>(data);
                for (size_t i = 0; i < self.layer_count; ++i)
                    if (self.game_mask & (uint32_t(1) << i))
                    {
                        self.applied.at(self.applies) = self.layers.at(i);
                        break;
                    }
                return self.results.at(self.applies++);
            },
            [](void *data) {
                auto &self = *static_cast<ScanoutFixture *>(data);
                return self.composition.at(self.applies - 1);
            },
        };
    }

    int apply(void *instance, uint32_t mask)
    {
        game_mask = mask;
        const auto callbacks = ops();
        return api().scanout(instance, mask, &callbacks);
    }
};

static void check_scanout()
{
    Context context;
    void *state = context.instance;
    ScanoutFixture choose;
    choose.pipelines = {0, 11, 11, 22};
    choose.pipeline_count = 4;
    choose.layers.fill(99);
    choose.results = {-EINVAL, 0};
    CHECK(choose.apply(state, 5) == 0);
    CHECK(choose.applies == 2 && choose.applied[0] == 11 && choose.applied[1] == 22);
    CHECK(choose.layers[0] == 22 && choose.layers[2] == 22);
    CHECK(choose.layers[1] == 0 && choose.layers[3] == 0);
    CHECK(choose.unsets == 2 && choose.sets == 4);

    ScanoutFixture preferred;
    preferred.pipelines = {11, 22};
    preferred.pipeline_count = 2;
    CHECK(preferred.apply(state, 1) == 0);
    CHECK(preferred.applies == 1 && preferred.applied[0] == 22);

    ScanoutFixture sdr;
    sdr.layers.fill(99);
    CHECK(sdr.apply(state, 0) == 0);
    CHECK(sdr.applies == 1 && !sdr.pipeline_reads && !sdr.sets && sdr.unsets == 4);
    CHECK(std::all_of(sdr.layers.begin(), sdr.layers.begin() + 4, [](auto value) { return value == 0; }));

    ScanoutFixture cached;
    cached.pipelines = {11, 22};
    cached.pipeline_count = 2;
    CHECK(cached.apply(state, 1) == 0 && cached.applied[0] == 22);

    ScanoutFixture disappeared;
    disappeared.pipelines = {11};
    disappeared.pipeline_count = 1;
    CHECK(disappeared.apply(state, 1) == 0);
    CHECK(disappeared.applies == 1 && disappeared.applied[0] == 11);

    ScanoutFixture retry;
    retry.pipelines = {22, 11, 33};
    retry.pipeline_count = 3;
    retry.results = {-EINVAL, 0, 0};
    retry.composition = {0, 1, 0};
    CHECK(retry.apply(state, 1) == 0);
    CHECK(retry.applies == 3 && retry.applied[0] == 11 && retry.applied[1] == 22 && retry.applied[2] == 33);

    ScanoutFixture fatal;
    fatal.pipelines = {33, 11};
    fatal.pipeline_count = 2;
    fatal.results = {-ENOMEM, 0};
    CHECK(fatal.apply(state, 1) == -ENOMEM);
    CHECK(fatal.applies == 1);

    ScanoutFixture after_fatal;
    after_fatal.pipelines = {11, 33};
    after_fatal.pipeline_count = 2;
    CHECK(after_fatal.apply(state, 1) == 0 && after_fatal.applied[0] == 11);

    ScanoutFixture fallback;
    fallback.pipelines = {11, 22};
    fallback.pipeline_count = 2;
    fallback.composition = {1, 1};
    CHECK(fallback.apply(state, 1) == -EINVAL);
    CHECK(fallback.applies == 2);

    ScanoutFixture no_pipeline;
    no_pipeline.pipeline_count = 2;
    no_pipeline.results = {-EAGAIN};
    CHECK(no_pipeline.apply(state, 1) == -EAGAIN);
    CHECK(no_pipeline.applies == 1 && !no_pipeline.sets);

    ScanoutFixture last_layer;
    last_layer.layer_count = 32;
    last_layer.pipelines = {44};
    last_layer.pipeline_count = 1;
    CHECK(last_layer.apply(state, uint32_t(1) << 31) == 0);
    CHECK(last_layer.layers[31] == 44 && last_layer.sets == 1 && last_layer.unsets == 31);

    ScanoutFixture too_many_layers;
    too_many_layers.layer_count = 33;
    CHECK(too_many_layers.apply(state, 1) == -EINVAL);
    CHECK(!too_many_layers.applies && !too_many_layers.sets && !too_many_layers.unsets);
}

int main()
{
    check_interface();
    check_math();
    check_policy();
    check_present();
    check_scanout();
    std::printf("Passed %u standalone AutoHDR checks\n", checks);
}
