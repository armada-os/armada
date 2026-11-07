#include "gamescope-color-provider.h"

int main(void)
{
    const gamescope_color_provider *provider = gamescope_color_provider_get_interface(GAMESCOPE_COLOR_PROVIDER_ABI);
    if (!gamescope_color_provider_is_compatible(provider))
        return 1;
    void *instance = provider->create();
    if (!instance)
        return 1;
    const gamescope_color_config config = {
        {1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f},
        100.0f, 1000.0f, 1.0f,
    };
    const gamescope_color_plan plan = provider->configure(instance, &config);
    const gamescope_color_rgb input = {100.0f, 50.0f, 25.0f};
    const gamescope_color_rgb output = plan.map(input, plan.data);
    provider->destroy(instance);
    return !(output.r > output.g && output.g > output.b);
}
