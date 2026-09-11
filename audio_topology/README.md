# Audio Topology

Source files for Armada's Qualcomm AudioReach topology blobs.

Only the generated topology blobs under the following directory are copied into
the firmware image; the `.m4` sources remain in this directory.

```text
system_files/usr/lib/firmware/qcom/sm8750/
```

To regenerate a topology using [audioreach-topology](https://git.codelinaro.org/linaro/qcomlt/audioreach-topology):

```sh
m4 -I <audioreach-topology> sm8750/SM8750-AYN.m4 > SM8750-AYN.conf
alsatplg -c SM8750-AYN.conf -o SM8750-AYN-tplg.bin
```

Replace the corresponding `-tplg.bin` in `system_files` after regeneration.
