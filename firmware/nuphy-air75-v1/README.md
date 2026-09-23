# Prebuilt images for the NuPhy Air75 (V1)

| Image | Layout |
| --- | --- |
| `nuphy-air75_ansi_smk.hex` | `ansi`: plain US ANSI |
| `nuphy-air75_usjis_smk.hex` | `usjis`: adds US-JIS, the IME keys beside Space and the Caps Lock / Left Ctrl swap |

Both are built from this repository's source with meson's defaults (debug build, sleep and ISP enabled) and SDCC 4.5.0 (built from source on macOS by `tools/macos/setup-toolchain.sh`):

```sh
meson setup build
meson compile -C build nuphy-air75_ansi_smk.hex nuphy-air75_usjis_smk.hex
```

Check a download with `shasum -a 256 -c SHA256SUMS`, back up the stock firmware, and write one image as the top-level README describes (`sinowisp write -d nuphy-air75 --force <image>`). See the top-level README for which image was checked on the board.
