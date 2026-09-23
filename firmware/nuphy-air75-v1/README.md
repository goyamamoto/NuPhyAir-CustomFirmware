# Prebuilt images for the NuPhy Air75 (V1)

| Image | Layout |
| --- | --- |
| `nuphy-air75_ansi_smk.hex` | `ansi`: plain US ANSI |
| `nuphy-air75_usjis_smk.hex` | `usjis`: adds US-JIS, the IME keys beside Space and the Caps Lock / Left Ctrl swap |

Both are release builds of this repository's source: no debug console and no logging, sleep and ISP enabled. They are built with SDCC 4.5.0 as below; the top-level README's [Building](../../README.md#building) section has the full steps, including the toolchain and how to check your build against `SHA256SUMS`:

```sh
meson setup build-release --buildtype=release
meson compile -C build-release nuphy-air75_ansi_smk.hex nuphy-air75_usjis_smk.hex
```

Check a download with `shasum -a 256 -c SHA256SUMS`, back up the stock firmware, and write one image as the top-level README describes (`sinowisp write -d nuphy-air75 --force <image>`). The `usjis` image is checked on the board; the `ansi` layout is checked on the board as a debug build, and its release image in the simulator.
