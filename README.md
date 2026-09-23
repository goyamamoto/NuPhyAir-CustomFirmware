# NuPhy Air75 (V1) custom firmware

[日本語](README.ja.md)

Open-source firmware for the original NuPhy Air75 (the first model, "V1"; MCU BYK916 = SinoWealth SH68F90A). QMK and ZMK do not run on this 8051-based MCU, so this is a port for [smk](https://github.com/carlossless/smk), the SinoWealth 8051 keyboard firmware by Karolis Stasaitis. This repository is smk with the Air75 added; everything smk supports still builds from it.

> [!WARNING]
> This replaces NuPhy's firmware and is experimental. You can go back to stock only with a backup of your own board (step 3); NuPhy's firmware is not distributed here. A firmware that cannot jump back to the bootloader can only be recovered with a hardware programmer (for example an Arduino Nano running [sinodude-serial](https://github.com/carlossless/sinodude)). This port adds a boot escape to make that unlikely, but use it at your own risk.

## What it does

- All keys, the Mac/Win switch, per-key RGB and the side lights, settings kept across power cycles
- USB, Bluetooth (three slots named `Air75-1` to `Air75-3`) and the 2.4 GHz dongle
- Sleep: on Bluetooth after about 5 minutes idle (a key wakes it), and over USB together with the host
- **Apple fn**: on macOS the F-row behaves as on an Apple keyboard (media keys, F1-F12 with Fn)
- **US-JIS** (Fn+Tab, `usjis` layout): type what the US keycaps show on a host set to the Japanese keyboard layout (Win layer)
- **IME keys** beside Space (`usjis` layout): tap for Eisu/Kana (Mac) or Muhenkan/Henkan (Win), hold for Command/Alt
- Caps Lock and Left Ctrl swapped (`usjis` layout)
- **Boot escape**: hold Esc while the keyboard powers up and it starts the bootloader instead, before any of this firmware's own USB code runs

## Pick a layout

Every image has the Apple fn key, the boot escape, the Bluetooth names and sleep. Pick a layout for what else you want:

| Layout | Adds | Image |
| --- | --- | --- |
| `ansi` | nothing: plain US ANSI, Caps Lock and Ctrl where they are printed | `nuphy-air75_ansi_smk.hex` |
| `usjis` | US-JIS (Fn+Tab), the IME keys beside Space, Caps Lock / Left Ctrl swapped | `nuphy-air75_usjis_smk.hex` |

## Supported keyboards

| Keyboard | USB ID | Status |
| --- | --- | --- |
| NuPhy Air75, first model (V1), ANSI | 05ac:024f, product "Air75" | Works; checked on the board with macOS hosts over USB, Bluetooth and the 2.4 GHz dongle (US-JIS in the Win layer) |

Not for the Air75 V2 or V3: those use an STM32 and run NuPhy's QMK-based firmware. For the NuPhy Air60 V2, see the QMK port in [goyamamoto/qmk-firmware](https://github.com/goyamamoto/qmk-firmware/tree/air60v2).

## Steps

1. **Check the keyboard.** Plug it in by USB. It must show up as USB ID `05ac:024f`, product "Air75" (macOS: System Information > USB).
2. **Install the tools.** Install [sinowisp](https://github.com/carlossless/sinowisp) with `cargo install sinowisp` (it reads and writes the flash through the stock bootloader over USB). On macOS, run it from a terminal app that has Input Monitoring permission (System Settings > Privacy & Security > Input Monitoring); without it the keyboard cannot be opened.
3. **Back up the stock firmware.** Keep both files somewhere safe; they are your only way back.
   ```sh
   sinowisp read -d nuphy-air75 air75-stock.hex                 # the firmware, for restoring (step 8)
   sinowisp read -d nuphy-air75 -s full air75-stock-full.hex    # firmware and bootloader, as an archive
   ```
   Reading twice and comparing the files is a cheap check that the read is stable.
4. **Get the firmware.** Pick a layout (above) and either use its image in [firmware/nuphy-air75-v1](firmware/nuphy-air75-v1) (check it with `shasum -a 256 -c SHA256SUMS`), or build it (see [Building](#building)).
5. **Write it.** Connect by USB, set the power switch to the USB position, and unplug any other keyboard with USB ID 05ac:024f (some Keychron boards use it too).
   ```sh
   sinowisp write -d nuphy-air75 --force nuphy-air75_usjis_smk.hex    # or nuphy-air75_ansi_smk.hex
   ```
   `--force` is needed because the image is smaller than the flash; sinowisp fills the rest with zeros, which also resets the settings.
6. **Check the ways back before anything else.**
   - With the new firmware running, `sinowisp read -d nuphy-air75 check.hex` must work.
   - Unplug USB, switch the power off, hold Esc, switch to USB and plug in, then let go of Esc after two seconds: the keyboard must show up as `0603:1020` ("SINO WEALTH" / "Gaming KB"), the bootloader. Unplug and plug in again without Esc to go back to the firmware.

   If a later build ever breaks USB, the second way still gets you to the bootloader.
7. **Use it.** See [Key map](#key-map). On macOS, keep "Use F1, F2, etc. keys as standard function keys" off to get media keys by default, as on an Apple keyboard.
8. **Back to stock** at any time:
   ```sh
   sinowisp write -d nuphy-air75 air75-stock.hex
   ```

## Key map

| Where | What |
| --- | --- |
| Base layers | US ANSI 75 %. The two keys between F12 and Del send PrtSc and Insert (macOS shows them as F13 and Help). `usjis`: Caps Lock and Left Ctrl are swapped |
| Keys beside Space | `ansi`: Command (Mac) / Alt (Win). `usjis`: Mac: tap = Eisu (left) / Kana (right), hold = Command. Win: tap = Muhenkan / Henkan, hold = Alt. They become the modifier when held for about 0.4 s or as soon as another key is pressed |
| F-row, Mac layer | F1-F4 and F7-F12 (macOS turns them into media keys unless Fn is held); F5/F6 dim and brighten the backlight, Fn+F5/F6 give F5/F6 |
| F-row, Win layer | F1-F12; Fn gives the media keys |
| Fn + Tab | `usjis`: US-JIS on/off (the side light flashes magenta for on, dim white for off). Substitutes only in the Win layer; saved across power cycles. `ansi`: Tab |
| Fn + Q / W / E | Bluetooth slot 1 / 2 / 3; hold about 6 s to pair (the status light blinks) |
| Fn + R | 2.4 GHz |
| Fn + [ / ] / \\ | Battery level: show briefly / always / off |
| Fn + arrows, `,` `.` | Effect previous/next (←/→), brightness (↑/↓), animation speed (`,`/`.`) |
| Fn + / (held) | The lighting keys act on the side lights instead |
| Fn + Esc (held), then Fn + V | Factory reset of the settings |

The upper-left side light shows the connection: orange = USB, blue = Bluetooth, green = 2.4 GHz, light green = Caps Lock on; blinking while pairing.

## Building

The firmware is built with [SDCC](https://sdcc.sourceforge.net/) 4.5.0 and meson. With [Nix](https://nixos.org/), `nix develop` gives the toolchain, sinowisp and the patched simulator. On macOS without Nix, [tools/macos/setup-toolchain.sh](tools/macos/setup-toolchain.sh) builds SDCC 4.5.0 and the simulator into `~/.local/smk`.

```sh
meson setup build
meson compile -C build nuphy-air75_usjis_smk.hex nuphy-air75_ansi_smk.hex
python3 -m unittest discover -s tests -p test_air75.py        # board tests in the simulator (both layouts)
python3 -m unittest discover -s tests -p test_air75_usjis.py  # US-JIS tests (a few minutes)
```

Technical notes for the board (pins, Apple fn, US-JIS, mod-taps, boot escape) are in [docs/keyboards/nuphy-air75.md](docs/keyboards/nuphy-air75.md). The upstream smk README is kept in [docs/README-smk.md](docs/README-smk.md).

## Known limitations

- Writing any image resets the settings (sinowisp zero-fills the settings area); the link then starts on Bluetooth slot 1.
- The prebuilt image is a debug build: it also carries smk's HID debug console (read with `tools/smk-console`).
- Pairing needs a hold of about 6 s (the stock firmware takes 3-4 s).
- US-JIS works only in the Win layer: macOS drops the JIS-only keys some of the substitutions need.
- The `ansi` image has been checked in the simulator only; the `usjis` code is what was checked on the board.

## Changes from upstream smk

Based on smk at [69373bb](https://github.com/carlossless/smk/commit/69373bbb633bd1159f4541f486ff7506563a38ec) (2026-09-16); changes made in 2026-09.

- New board: `src/keyboards/nuphy-air75/` (layouts `ansi` and `usjis`), `docs/keyboards/nuphy-air75.md`, `tests/test_air75.py`, `tests/test_air75_usjis.py`
- New optional features, off unless a board enables them: US-JIS (`src/smk/usjis.c/.h`, `USJIS`), mod-tap keys (`src/smk/tap_hold.c/.h`, `TAP_HOLD`, plus `MT()` helpers in `src/smk/keycodes.h`), Apple fn byte (`APPLE_FN`: `src/smk/report.c/.h`, `src/smk/usb.c`, `src/smk/keyboard.c`, `src/smk/matrix.c`, RF byte 9 in `src/peripherals/bk3632/rf_controller.c`), per-slot Bluetooth names (`RF_BT_NAME`, `rf_controller.c`), boot escape (`BOOT_ESCAPE`: `src/main.c`, `src/user/user_init.h`), `defines` options per keyboard and per layout (`meson.build`)
- Shared changes: `tick_scans()` scan counter (`src/smk/tick.c/.h`), `process_keycode()` split out of the matrix (`src/smk/matrix.c/.h`), board hook `kb_layer_is_apple_fn()` (`src/kb/kb.h`), settings field for US-JIS (`src/smk/settings.c/.h`), debug-build logging of SET_REPORT/LED requests (`src/smk/usb.c`), the simulator reading P7.0/P7.5/P7.7 as pins (`tools/ucsim/sh68f90.cc`), the Air75 in `src/keyboards/meson.build`
- `README.md` replaced by this file; the upstream one moved to `docs/README-smk.md`. New: `README.ja.md`, `firmware/`, `tools/macos/`

## Credits and license

- [smk](https://github.com/carlossless/smk), [sinowisp](https://github.com/carlossless/sinowisp) and [sinodude](https://github.com/carlossless/sinodude) by Karolis Stasaitis, whose reverse engineering of the NuPhy Air60 made this possible.
- The US-JIS rules follow [goyamamoto/zmk-kb1-usjis](https://github.com/goyamamoto/zmk-kb1-usjis).
- License: GPL-2.0, as smk ([LICENSE](LICENSE)).

NuPhy is a trademark of its owner. This project is not affiliated with or endorsed by NuPhy.
