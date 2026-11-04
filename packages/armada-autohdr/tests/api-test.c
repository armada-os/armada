#include "armada-autohdr.h"

int main(void)
{
    const armada_autohdr_transform transform = {
        {1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f},
        100.0f, 1000.0f,
    };
    const armada_autohdr_rgb input = {100.0f, 50.0f, 25.0f};
    const armada_autohdr_rgb output = armada_autohdr_apply_transform(&transform, input);
    return armada_autohdr_abi_version() != ARMADA_AUTOHDR_ABI_VERSION ||
        !(output.r > output.g && output.g > output.b);
}
