# Prebuilt image for the NuPhy Air75 (V1)

`nuphy-air75_default_smk.hex` is the image that was written to and checked on an Air75 (see the list in the top-level README). It is built from this repository's source with meson's defaults (debug build, sleep and ISP enabled) and SDCC 4.5.0:

```sh
meson setup build
meson compile -C build nuphy-air75_default_smk.hex
```

A rebuild of this tree with SDCC 4.5.0 (built from source on macOS by `tools/macos/setup-toolchain.sh`) gave the same bytes; check a download with `shasum -a 256 -c SHA256SUMS`. Write it as described in the top-level README (`sinowisp write -d nuphy-air75 --force nuphy-air75_default_smk.hex`), after backing up the stock firmware.
