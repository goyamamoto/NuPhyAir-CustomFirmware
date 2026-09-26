#!/usr/bin/env python3
"""nuphy-air75: checks for the defects found by the 2026-09-26 review of
build-8 (5e0508e), driven through the patched uCsim simulator. Every class
fails on the build-8 images (see each class for what it pins down) and passes
on the fixed ones.

Run from the repo root after building the firmware (see test_air75.py):

    python3 -m unittest discover -s tests -p test_air75_fixes.py
"""

import re
import unittest

from test_air75 import (AIR75_FW, AIR75_ANSI_FW, Air75Sim, TestAppleFn, _need_firmware,
                        read_ihex, MOD_LALT)

FN = (9, 5)
KEY = {
    "Right": (15, 5), "Esc": (0, 0), "Up": (14, 4), "Q": (1, 2), "LBrc": (11, 2),
    "Tab": (0, 2), "F1": (1, 0), "F11": (11, 0), "A": (1, 3), "ImeL": (2, 5),
}
HID = {"Right": 0x4F, "Esc": 0x29, "Up": 0x52, "Q": 0x14, "LBrc": 0x2F, "RBrc": 0x30,
       "Tab": 0x2B, "F1": 0x3A, "F11": 0x44}
BRIGHTNESS_DOWN, AUDIO_VOL_DOWN = 0x0070, 0x00EA
REPORT_ID_SYSTEM, REPORT_ID_CONSUMER = 1, 2
USJIS_OFFSET = 9          # user_settings.usjis_enabled (test_air75_usjis.py)
USBCON, USBIF1 = 0x91, 0x92
WKUP, RESMIF, SUSPIF, SETUPIF = 0x02, 0x04, 0x02, 0x10
SET_FEATURE_REMOTE_WAKEUP = [0x00, 0x03, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
CLEAR_FEATURE_REMOTE_WAKEUP = [0x00, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
GET_STATUS_DEVICE = [0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00]
P0 = 0x80                 # BK3632 MISO on P0.6 (the model reads the P0 latch)
MISO_BIT = 0x40
SYSTEM_SLEEP = 0x0082
P4 = 0xB0                 # BK3632 ACK on P4.2 (the model reads the P4 latch)
ACK_BIT = 0x04

# The four orders of a key K and Fn going down and up.
ORDERS = {
    "K Fn K' Fn'": [("down", "K"), ("down", "Fn"), ("up", "K"), ("up", "Fn")],
    "K Fn Fn' K'": [("down", "K"), ("down", "Fn"), ("up", "Fn"), ("up", "K")],
    "Fn K K' Fn'": [("down", "Fn"), ("down", "K"), ("up", "K"), ("up", "Fn")],
    "Fn K Fn' K'": [("down", "Fn"), ("down", "K"), ("up", "Fn"), ("up", "K")],
}


def kb_report(*keys, mods=0, fn=0):
    keys = list(keys) + [0] * 5
    return ("1", [mods, 0] + keys[:5] + [fn])


def consumer(usage):
    return ("2", [REPORT_ID_CONSUMER, usage & 0xFF, usage >> 8])


def usb_stream(kb):
    """Every EP1 (keyboard) and EP2 (NKRO/consumer/system) report in the order
    the SIE logged them, as ("1"|"2", bytes)."""
    return [(ep, [int(x, 16) for x in data.split()])
            for ep, data in re.findall(r"\[SIE\] EP([12]) IN \d+ bytes:((?: [0-9a-f]{2})*)", kb.stderr_text())]


def iram_bit(kb, bit_addr):
    byte, mask = 0x20 + (bit_addr >> 3), 1 << (bit_addr & 7)
    return 1 if kb.get_iram(byte, 1)[0] & mask else 0


def set_iram_bit(kb, bit_addr, value):
    byte, mask = 0x20 + (bit_addr >> 3), 1 << (bit_addr & 7)
    v = kb.get_iram(byte, 1)[0]
    v = (v | mask) if value else (v & ~mask)
    kb.cmd("set mem iram 0x%x 0x%02x" % (byte, v))


class FixSim(Air75Sim):
    def bit_symbol(self, module, name):
        """Bit address of a __bit variable: from the .map for a global, else from
        the linker listing <image>.ihx.p/<module>.rst (a static)."""
        if name in self.sym:
            return self.sym[name]
        rst = re.sub(r"\.hex$", ".ihx.p", self.firmware) + "/" + module + ".rst"
        pat = re.compile(r"^\s+([0-9A-F]{6})\s+\d+ _%s::?$" % re.escape(name))   # BSEG label = bit address
        with open(rst) as f:
            for line in f:
                m = pat.match(line)
                if m:
                    return int(m.group(1), 16)
        raise KeyError("%s$%s not found" % (module, name))

    def skip_power_down(self):
        """Replace `ORL PCON,#0x02` (right after `MOV SUSLO,#0x55`) with NOPs:
        this simulator build does not wake from power-down, so the test plays
        the wake itself at clock_wake_restart."""
        img = read_ihex(self.firmware)
        code = bytes(img.get(i, 0) for i in range(max(img) + 1))
        at = code.find(bytes([0x75, 0x8E, 0x55, 0x43, 0x87, 0x02]))
        if at < 0 or code.find(bytes([0x75, 0x8E, 0x55, 0x43, 0x87, 0x02]), at + 1) >= 0:
            raise AssertionError("power-down instruction not found once")
        self.cmd("set mem rom 0x%x 0x00 0x00 0x00" % (at + 3))

    def call(self, func, dptr=None, resume_pc=None):
        """Run func() once from the current stop, as a call from the main loop:
        a return address to a NOP sled is pushed, interrupts stay as they are,
        and afterwards SP and PC are put back (resume_pc, default the current
        breakpoint's address). dptr: the first argument (DPL/DPH)."""
        sp = self.get_sfr(0x81)
        self.cmd("set mem rom 0x9000 0x00 0x00 0x00 0x00")
        self.cmd("set mem iram 0x%x 0x00" % (sp + 1))
        self.cmd("set mem iram 0x%x 0x90" % (sp + 2))
        self.set_sfr(0x81, sp + 2)
        if dptr is not None:
            self.set_sfr(0x82, dptr & 0xFF)
            self.set_sfr(0x83, dptr >> 8)
        self.cmd("pc 0x%x" % self._a(func))
        self.brk(0x9000)
        self.run()
        self.cmd("delete")
        self.set_sfr(0x81, sp)
        self.cmd("pc 0x%x" % resume_pc)

    def setup_packet(self, setup):
        """Hand the firmware a control SETUP through EP0 (the SIE raises the
        USB interrupt on SETUPIF) and let it run a little."""
        self.cmd("set mem xram 0x1100 " + " ".join("0x%02x" % b for b in setup))
        self.set_sfr(USBIF1, SETUPIF)
        TestAppleFn._run(self, 40)

    def ep0_in(self):
        return [[int(x, 16) for x in m.split()]
                for m in re.findall(r"\[SIE\] EP0 IN\[\d+\] \d+ bytes:((?: [0-9a-f]{2})*)", self.stderr_text())]

    def miso_read_address(self):
        """The instruction in bb_spi_xfer_byte that samples MISO (P0.6, bit
        address 0x86): JB/JNB/MOV C,bit with operand 0x86."""
        img = read_ihex(self.firmware)
        start = self._a("bb_spi_xfer_byte")
        for a in range(start, start + 0x60):
            if img.get(a) in (0x20, 0x30, 0xA2) and img.get(a + 1) == 0x86:
                return a
        raise AssertionError("MISO sample not found in bb_spi_xfer_byte")

    def restore_rom(self, name):
        """Undo the RET that reset_fast() puts on a delay routine."""
        addr = self._a(name)
        self.cmd("set mem rom 0x%x 0x%02x" % (addr, read_ihex(self.firmware)[addr]))


class Case(unittest.TestCase):
    FIRMWARE = AIR75_FW
    HITS = 120            # row reads per event: about four scans

    @classmethod
    def setUpClass(cls):
        _need_firmware()

    def session(self, usb=True, mac=False, usjis=False, firmware=None):
        kb = FixSim(firmware or self.FIRMWARE)
        self.addCleanup(kb.close)
        kb.boot(usb=usb, mac=mac)
        if usb:
            kb.mark_usb_configured()
        if usjis:
            kb.cmd("set mem xram 0x%x 0x01" % (kb._a("user_settings") + USJIS_OFFSET))
        return kb

    def run_scans(self, kb, hits=None):
        TestAppleFn._run(kb, hits or self.HITS)

    def play(self, kb, events, keys):
        """events: [("down"|"up", name)], keys: {name: (col, row)}. Returns, per
        event, the USB reports that went out after it."""
        out = []
        for action, name in events:
            pos = keys[name]
            (kb.matrix.press if action == "down" else kb.matrix.release)(*pos)
            before = len(usb_stream(kb))
            self.run_scans(kb)
            out.append(usb_stream(kb)[before:])
        return out


class TestKeysAcrossFn(Case):
    """A key goes up on the host with what it went down with, whatever Fn did
    in between, and Fn going up sends the report for the keys it clears (so a
    key still held then goes up there, and nothing more at its own release)."""

    @staticmethod
    def streams(base, fn_down=(), fn_up=()):
        """The expected reports per event for a key whose base keycode sends
        `base` and whose Fn-layer entry sends `fn_down` / `fn_up` (a board key
        sends nothing; a consumer usage goes up only with the key)."""
        up = [kb_report()]
        fn_down, fn_up = list(fn_down), list(fn_up)
        return {
            "K Fn K' Fn'": [base, [], up, []],
            "K Fn Fn' K'": [base, [], up, []],
            "Fn K K' Fn'": [[], fn_down, fn_up, []],
            "Fn K Fn' K'": [[], fn_down, [], fn_up],
        }

    def check_key(self, name, expected, mac=False, usjis=False, extra=None):
        keys = {"K": KEY[name], "Fn": FN}
        kb = self.session(mac=mac, usjis=usjis)
        for order, events in ORDERS.items():
            with self.subTest(key=name, order=order, mac=mac):
                got = self.play(kb, events, keys)
                self.assertEqual(got, expected[order], "report stream per event")
                if extra:
                    extra(kb, order)
            kb.matrix.clear()
            self.run_scans(kb)

    def test_right_under_fn_is_a_lighting_key(self):
        self.check_key("Right", self.streams([kb_report(HID["Right"])]))

    def test_up_under_fn_is_a_lighting_key(self):
        self.check_key("Up", self.streams([kb_report(HID["Up"])]))

    def test_q_under_fn_is_a_link_key(self):
        self.check_key("Q", self.streams([kb_report(HID["Q"])]))

    def test_esc_under_fn_is_the_reset_hold(self):
        def reset_hold_released(kb, order):
            flag = kb._xdata_static("kb", "reset_mode_active")
            self.assertEqual(kb.get_xram(flag)[0], 0, "RST_HLD must not stay armed after %s" % order)
        self.check_key("Esc", self.streams([kb_report(HID["Esc"])]), extra=reset_hold_released)

    def test_lbrc_in_usjis_is_substituted_and_bat_fl_under_fn(self):
        self.check_key("LBrc", self.streams([kb_report(HID["RBrc"])]), usjis=True)

    def test_tab_in_usjis_is_the_usjis_toggle_under_fn(self):
        self.check_key("Tab", self.streams([kb_report(HID["Tab"])]), usjis=True)

    def test_win_f1_under_fn_is_brightness_down(self):
        self.check_key("F1", self.streams([kb_report(HID["F1"])],
                                          [consumer(BRIGHTNESS_DOWN)], [consumer(0)]))

    def test_win_f11_under_fn_is_volume_down(self):
        self.check_key("F11", self.streams([kb_report(HID["F11"])],
                                           [consumer(AUDIO_VOL_DOWN)], [consumer(0)]))

    def test_mac_f1_under_fn_carries_the_apple_fn_byte(self):
        """Mac Fn+F1 is F1 with the Apple fn byte: fn goes out first, alone,
        then with the key; Fn going up clears both."""
        f1, fn_alone = kb_report(HID["F1"]), kb_report(fn=1)
        up = kb_report()
        self.check_key("F1", {
            "K Fn K' Fn'": [[f1], [], [up], []],
            "K Fn Fn' K'": [[f1], [], [up], []],
            "Fn K K' Fn'": [[], [fn_alone, kb_report(HID["F1"], fn=1)], [fn_alone], [up]],
            "Fn K Fn' K'": [[], [fn_alone, kb_report(HID["F1"], fn=1)], [up], []],
        }, mac=True)

    def test_ime_mod_tap_across_fn_leaves_no_modifier(self):
        """Left IME key (Win: Alt when held) with Fn: Fn going down makes it a
        hold; in either release order the Alt goes up."""
        kb = self.session()
        keys = {"K": KEY["ImeL"], "Fn": FN}
        alt, up = kb_report(mods=MOD_LALT), kb_report()
        for order, want in [("K Fn K' Fn'", [[], [alt], [up], []]),
                            ("K Fn Fn' K'", [[], [alt], [], [up]])]:
            with self.subTest(order=order):
                self.assertEqual(self.play(kb, ORDERS[order], keys), want)


class TestKeysAcrossFnAnsi(TestKeysAcrossFn):
    """The same on the ansi image (no US-JIS, no mod-taps): [ is [, Fn+Tab is Tab."""
    FIRMWARE = AIR75_ANSI_FW

    def test_lbrc_in_usjis_is_substituted_and_bat_fl_under_fn(self):
        self.check_key("LBrc", self.streams([kb_report(HID["LBrc"])]))

    def test_tab_in_usjis_is_the_usjis_toggle_under_fn(self):
        tab, up = kb_report(HID["Tab"]), kb_report()
        self.check_key("Tab", {
            "K Fn K' Fn'": [[tab], [], [up], []],
            "K Fn Fn' K'": [[tab], [], [up], []],
            "Fn K K' Fn'": [[], [tab], [up], []],
            "Fn K Fn' K'": [[], [tab], [up], []],
        })

    def test_ime_mod_tap_across_fn_leaves_no_modifier(self):
        raise unittest.SkipTest("the ansi layout has no mod-taps")


class PairingCase(Case):
    Q = KEY["Q"]

    def frames(self, kb, iterations, stop_on=None):
        """rf_tx_buf at every bb_spi_xfer call, servicing the matrix meanwhile."""
        xfer, buf, rr = kb._a("bb_spi_xfer"), kb._a("rf_tx_buf"), kb._a("user_matrix_read_rows")
        kb.brk(xfer)
        kb.brk(rr)
        out = []
        for _ in range(iterations):
            at = kb.stopped_at(kb.run())
            if at == rr:
                kb.matrix.inject(kb)
                continue
            f = kb.get_xram(buf, 6)
            out.append(f)
            if stop_on and f[:len(stop_on)] == stop_on:
                break
        kb.cmd("delete")
        return out

    def hold_link_key(self, kb):
        kb.matrix.press(*FN)
        self.run_scans(kb)
        kb.matrix.press(*self.Q)
        held = kb._xdata_static("kb", "link_hold_keycode")
        for _ in range(20):
            self.run_scans(kb, 40)
            if any(kb.get_xram(held, 2)):
                return
        self.fail("the link key press was not registered")

    def skip_to(self, kb, scans_after_press):
        since = kb._xdata_static("kb", "link_hold_since")
        lo, hi = kb.get_xram(since, 2)
        target = ((lo | (hi << 8)) + scans_after_press) & 0xFFFF
        clock = kb._xdata_static("tick", "scans")
        kb.cmd("set mem xram 0x%x 0x%02x 0x%02x" % (clock, target & 0xFF, target >> 8))

    def slide(self, kb, usb):
        """Move the connection slider and run until the firmware applies it."""
        kb.matrix.usb_mode = usb
        kb.matrix.inject(kb)
        target = kb._a("rf_apply_usb_mode" if usb else "rf_kbd_lazy_state_init")
        rr = kb._a("user_matrix_read_rows")
        kb.brk(target)
        kb.brk(rr)
        for _ in range(2000):
            at = kb.stopped_at(kb.run())
            if at == target:
                break
            kb.matrix.inject(kb)
        else:
            self.fail("slider change to %s not applied" % ("USB" if usb else "RF"))
        kb.cmd("delete")
        self.run_scans(kb, 64)

    PAIR = [0xAA, 0x03, 0x01, 0x01]

    def assertNoPairing(self, kb):
        self.skip_to(kb, 4400 + 10)          # LINK_PAIRING_HOLD_SCANS, about 6 s
        frames = self.frames(kb, 1500, stop_on=self.PAIR)
        self.assertNotIn(self.PAIR, [f[:4] for f in frames], "pairing command sent")


class TestPairingArm(PairingCase):
    def test_fn_released_first_does_not_pair(self):
        kb = self.session(usb=False)
        self.hold_link_key(kb)
        kb.matrix.release(*FN)
        self.run_scans(kb)
        kb.matrix.release(*self.Q)
        self.run_scans(kb)
        self.assertNoPairing(kb)

    def test_short_tap_does_not_pair(self):
        kb = self.session(usb=False)
        self.hold_link_key(kb)
        kb.matrix.release(*self.Q)
        self.run_scans(kb)
        kb.matrix.release(*FN)
        self.run_scans(kb)
        self.assertNoPairing(kb)

    def test_slider_change_mid_hold_does_not_pair(self):
        """Fn+Q held in wireless, slider to USB, keys up there, slider back to
        wireless: nothing may pair."""
        kb = self.session(usb=False)
        self.hold_link_key(kb)
        self.slide(kb, usb=True)
        kb.matrix.clear()
        self.run_scans(kb)
        self.slide(kb, usb=False)
        self.assertNoPairing(kb)

    def test_slider_round_trip_with_the_key_still_held_does_not_pair(self):
        kb = self.session(usb=False)
        self.hold_link_key(kb)
        self.slide(kb, usb=True)
        self.slide(kb, usb=False)
        self.assertNoPairing(kb)

    def test_long_hold_still_pairs(self):
        kb = self.session(usb=False)
        self.hold_link_key(kb)
        self.skip_to(kb, 4400 - 10)
        frames = self.frames(kb, 3000, stop_on=self.PAIR)
        self.assertIn(self.PAIR + [0x01], [f[:5] for f in frames])


class TestRfRetries(Case):
    """The simulator has no radio: the ACK line (P4.2) never changes unless the
    test flips it, so every frame is a missed ACK until then."""

    A = KEY["A"]

    def attempts(self, kb, length, ack_on=None, limit=40, stop=None):
        """rf_tx_buf (length bytes) at each bb_spi_xfer entry. ack_on: the
        attempt numbers (1-based) at which the radio ACKs: the ACK line (P4.2)
        drops at that attempt's first poll (its second delay_us; the first is
        the wake-up inside the burst) and comes back up when bb_spi_xfer
        returns. (The line must not stay low in this simulator: its 8051 core
        takes P4.2, the standard P3.2, for INT0 and then keeps setting TCON.IE0,
        which on this chip is P5.1, a column.) Stops after `limit` frames or
        when stop(frames) is true."""
        xfer, buf, du = kb._a("bb_spi_xfer"), kb._a("rf_tx_buf"), kb._a("delay_us")
        rr = kb._a("user_matrix_read_rows")
        kb.brk(xfer)
        kb.brk(du)
        kb.brk(rr)
        self.assertTrue(kb.get_sfr(P4) & ACK_BIT, "ACK line idles high")
        frames, delays, ret = [], 0, None
        for _ in range(20000):
            at = kb.stopped_at(kb.run())
            if at == rr:
                kb.matrix.inject(kb)
            elif at == xfer:
                if ret is None:
                    sp = kb.get_sfr(0x81)
                    lo, hi = kb.get_iram(sp - 1, 2)
                    ret = lo | (hi << 8)
                    kb.brk(ret)
                frames.append(kb.get_xram(buf, length))
                delays = 0
                if len(frames) >= limit or (stop and stop(frames)):
                    break
            elif at == du:
                delays += 1
                if delays == 2 and ack_on and len(frames) in ack_on:
                    kb.set_sfr(P4, kb.get_sfr(P4) & ~ACK_BIT & 0xFF)
            elif at == ret:
                kb.set_sfr(P4, kb.get_sfr(P4) | ACK_BIT)
        kb.cmd("delete")
        kb.set_sfr(P4, kb.get_sfr(P4) | ACK_BIT)
        return frames

    @staticmethod
    def report_frame(*keys):
        f = [0xAA, 0x1D, 0x02, 0x00] + list(keys) + [0] * (5 - len(keys)) + [0] + [0] * 21
        f.append((0x55 - sum(f)) & 0xFF)
        return f

    @staticmethod
    def extra_frame(consumer_usage, system_usage):
        f = [0xAA, 0x0B, 0x05, 0, 0, 0, 0, 0, 0, consumer_usage & 0xFF, consumer_usage >> 8,
             system_usage & 0xFF, system_usage >> 8]
        f.append((0x55 - sum(f)) & 0xFF)
        return f

    def rf_session(self):
        kb = self.session(usb=False, mac=False)
        self.run_scans(kb, 64)
        return kb

    def test_key_report_retries_carry_the_frame(self):
        """A missed ACK on the first attempt, an ACK on the second: both
        attempts carry the report, and it is not sent a third time."""
        kb = self.rf_session()
        kb.matrix.press(*self.A)
        want = self.report_frame(0x04)
        frames = self.attempts(kb, 32, ack_on={2}, limit=3)
        self.assertEqual(frames[:2], [want, want], "the first attempt and the retry after the missed ACK")
        self.assertNotEqual(frames[2:3], [want], "sent again after the ACK")

    def test_all_five_attempts_carry_the_frame(self):
        kb = self.rf_session()
        kb.matrix.press(*self.A)
        frames = self.attempts(kb, 32, limit=5)
        self.assertEqual(frames, [self.report_frame(0x04)] * 5)

    def test_five_attempts_in_one_send(self):
        """An unanswered report is tried five times in a row before the main
        loop moves on, not once per pass."""
        kb = self.rf_session()
        kb.matrix.press(*self.A)
        send, xfer, upd, rr = (kb._a(n) for n in ("rf_send_report", "bb_spi_xfer", "kb_update",
                                                  "user_matrix_read_rows"))
        kb.brk(send)
        kb.brk(rr)
        for _ in range(2000):
            if kb.stopped_at(kb.run()) == send:
                break
            kb.matrix.inject(kb)
        kb.cmd("delete")
        kb.brk(xfer)
        kb.brk(upd)
        n = 0
        while kb.stopped_at(kb.run()) == xfer:
            n += 1
        kb.cmd("delete")
        self.assertEqual(n, 5, "attempts before the main loop went on")

    def test_consumer_report_is_sent_until_acked(self):
        """Win Fn+F11 (Volume Down) over the radio: five attempts go unanswered,
        the report is sent again from the main loop, the ACK on attempt 7 ends
        it; the release is a separate frame."""
        kb = self.rf_session()
        kb.matrix.press(*FN)
        self.run_scans(kb)
        kb.matrix.press(*KEY["F11"])
        press = self.extra_frame(AUDIO_VOL_DOWN, 0)
        frames = self.attempts(kb, 14, ack_on={7}, limit=14,
                               stop=lambda fs: len(fs) > 7)
        self.assertEqual(frames[:7], [press] * 7, "the press, five attempts and two more until the ACK")
        self.assertNotEqual(frames[7:8], [press], "nothing more of the press after the ACK")
        kb.matrix.release(*KEY["F11"])
        release = self.extra_frame(0, 0)
        frames = self.attempts(kb, 14, ack_on={1}, limit=3,
                               stop=lambda fs: fs[-1][:3] == [0xAA, 0x0B, 0x05])
        self.assertEqual(frames[-1], release, "the release goes out")


class TestSliderRelease(PairingCase):
    """A key held while the connection slider moves goes up on the transport
    being left (its release would otherwise go to the new one): the keyboard
    report, the NKRO report when NKRO is in use, and the consumer and system
    usages."""

    def slide_reports(self, kb, usb):
        """Move the slider; return what was handed to the radio until the
        firmware has applied the change: (keyboard reports, rf_send_report's
        argument, 8 bytes; consumer/system reports, rf_send_extra's, 3 bytes)."""
        kb.matrix.usb_mode = usb
        kb.matrix.inject(kb)
        target = kb._a("rf_apply_usb_mode" if usb else "rf_kbd_lazy_state_init")
        send, extra, rr = kb._a("rf_send_report"), kb._a("rf_send_extra"), kb._a("user_matrix_read_rows")
        for a in (target, send, extra, rr):
            kb.brk(a)
        reports, extras = [], []
        for _ in range(40000):     # with no ACK, every pass retries a held key's report
            at = kb.stopped_at(kb.run())
            if at == target:
                break
            if at in (send, extra):
                ptr = kb.get_sfr(0x82) | (kb.get_sfr(0x83) << 8)     # DPTR = the report
                (reports if at == send else extras).append(kb.get_xram(ptr, 8 if at == send else 3))
            else:
                kb.matrix.inject(kb)
        else:
            self.fail("slider change not applied")
        kb.cmd("delete")
        return reports, extras

    RELEASED_EXTRAS = [[REPORT_ID_CONSUMER, 0, 0], [REPORT_ID_SYSTEM, 0, 0]]

    def test_usb_to_wireless_releases_the_key_on_usb(self):
        kb = self.session(usb=True)
        kb.matrix.press(*KEY["A"])
        self.run_scans(kb)
        self.assertEqual(kb.ep1_reports()[-1], kb_report(0x04)[1])
        before = len(usb_stream(kb))
        self.slide_reports(kb, usb=False)
        self.assertEqual(usb_stream(kb)[before:],
                         [kb_report()] + [("2", r) for r in self.RELEASED_EXTRAS],
                         "USB host must see the key, consumer and system usages go up")

    def test_usb_to_wireless_releases_nkro_on_usb(self):
        """NKRO is off on the Air75 (APPLE_FN), so it is switched on here the
        way a host with the Report protocol and the NKRO setting would have it."""
        kb = self.session(usb=True)
        kb.cmd("set mem xram 0x%x 0x01" % kb._a("keymap_config"))          # .nkro
        kb.cmd("set mem xram 0x%x 0x01" % kb._a("interface0_protocol"))    # Report protocol
        kb.matrix.press(*KEY["A"])
        self.run_scans(kb)
        a_down = [6, 0, 0x10] + [0] * 19                                   # usage 0x04 = byte 0, bit 4
        self.assertEqual(usb_stream(kb)[-1], ("2", a_down), "NKRO report on EP2")
        before = len(usb_stream(kb))
        self.slide_reports(kb, usb=False)
        self.assertIn(("2", [6] + [0] * 21), usb_stream(kb)[before:], "NKRO host must see the key go up")

    def test_wireless_to_usb_releases_the_key_on_the_radio(self):
        kb = self.session(usb=False)
        self.run_scans(kb, 64)
        kb.matrix.press(*KEY["A"])
        self.run_scans(kb)
        reports, extras = self.slide_reports(kb, usb=True)
        self.assertEqual(reports, [kb_report()[1]], "radio host must see the key go up")
        self.assertEqual(extras, self.RELEASED_EXTRAS, "and the consumer and system usages")


class TestRfPaths(PairingCase):
    """Radio paths the retry tests do not reach: the status reply read back
    over MISO, what is left pending across a slider round trip, and a
    consumer report after a system one."""

    attempts = TestRfRetries.attempts
    rf_session = TestRfRetries.rf_session
    extra_frame = staticmethod(TestRfRetries.extra_frame)
    slide_reports = TestSliderRelease.slide_reports

    def feed_status_reply(self, kb, reply):
        """Run until the firmware reads a status reply (rf_fetch_4) and present
        `reply` (4 bytes, MSB first) on MISO bit by bit: P0.6 is set before
        each sample instruction runs."""
        fetch, sample = kb._a("rf_fetch_4"), kb.miso_read_address()
        rr = kb._a("user_matrix_read_rows")
        kb.brk(fetch)
        kb.brk(rr)
        for _ in range(20000):
            at = kb.stopped_at(kb.run())
            if at == fetch:
                break
            kb.matrix.inject(kb)
        else:
            self.fail("no status read")
        kb.cmd("delete")
        kb.brk(sample)
        bits = [(byte >> (7 - i)) & 1 for byte in reply for i in range(8)]
        for bit in bits:
            self.assertEqual(kb.stopped_at(kb.run()), sample, "fewer MISO samples than the reply")
            p0 = kb.get_sfr(P0)
            kb.set_sfr(P0, (p0 | MISO_BIT) if bit else (p0 & ~MISO_BIT & 0xFF))
            kb.cmd("step")                                                  # the sample itself
        kb.cmd("delete")
        kb.set_sfr(P0, kb.get_sfr(P0) | MISO_BIT)                           # MISO idles high
        self.run_scans(kb, 64)

    def test_status_reply_is_read_back(self):
        """The link supervisor's status read: battery level 5, connected,
        paired, Bluetooth 1. A receive that dropped the MISO bytes would leave
        0xFF in the buffer and the state untouched."""
        kb = self.rf_session()
        kb.cmd("set mem xram 0x%x 0xcf 0x07" % kb._xdata_static("rf_controller", "supervisor_ticks"))  # 1999
        s0, s1 = 0x80 | 5, 0x08 | 0x10 | (1 << 5)
        self.feed_status_reply(kb, [0xBB, (0x55 - s0 - s1) & 0xFF, s0, s1])
        state = kb.get_xram(kb._a("keyboard_state"), 6)
        self.assertEqual(state[2], 5, "battery level from the reply: %s" % state)
        self.assertEqual((state[1], state[4], state[5]), (1, 1, 1), "link, connected, paired: %s" % state)

    def test_no_leftover_consumer_report_after_a_slider_round_trip(self):
        """Win Fn+F11 unanswered, slider to USB and back: entering wireless
        again sends nothing left over from before."""
        kb = self.rf_session()
        kb.matrix.press(*FN)
        self.run_scans(kb)
        kb.matrix.press(*KEY["F11"])
        self.run_scans(kb)
        self.slide_reports(kb, usb=True)
        kb.matrix.clear()
        self.run_scans(kb)
        self.slide_reports(kb, usb=False)
        xfer, buf, rr = kb._a("bb_spi_xfer"), kb._a("rf_tx_buf"), kb._a("user_matrix_read_rows")
        kb.brk(xfer)
        kb.brk(rr)
        frames, rows = [], 0
        while rows < 320:                                                   # ten scans
            if kb.stopped_at(kb.run()) == rr:
                kb.matrix.inject(kb)
                rows += 1
            else:
                frames.append(kb.get_xram(buf, 14))
        kb.cmd("delete")
        self.assertFalse([f for f in frames if f[:3] == [0xAA, 0x0B, 0x05]],
                         "a consumer/system frame left over: %s" % frames)

    def test_consumer_report_carries_no_stale_system_usage(self):
        """A system usage (Sleep) left pending by a missed ACK, then Win Fn+F11:
        the consumer frame has system 0, as a consumer report always had."""
        kb = self.rf_session()
        kb.brk(kb._a("kb_update"))
        kb.run()
        kb.cmd("delete")
        kb.call("host_system_send", dptr=SYSTEM_SLEEP, resume_pc=kb._a("kb_update"))
        kb.matrix.press(*FN)
        self.run_scans(kb)
        kb.matrix.press(*KEY["F11"])
        frames = self.attempts(kb, 14, limit=40, stop=lambda fs: fs[-1][9] == AUDIO_VOL_DOWN)
        self.assertEqual(frames[-1], self.extra_frame(AUDIO_VOL_DOWN, 0))


class TestWatchdog(Case):
    """The watchdog must reset a main loop that hangs with interrupts on. The
    delays run for real here (boot() stubs them): the Timer2 scan must not kick
    the watchdog from its settling delays."""

    def hang_and_count(self, hang, max_isr=4000):
        kb = FixSim(self.FIRMWARE)
        self.addCleanup(kb.close)
        kb.boot(usb=False, mac=False)          # wireless: no USB host
        kb.restore_rom("delay_us")
        kb.restore_rom("delay_ms")
        if hang:
            kb.cmd("set mem rom 0x9000 0x80 0xfe")   # SJMP $
            kb.brk(kb._a("kb_update"))
            kb.run()
            kb.cmd("delete")
            kb.cmd("pc 0x9000")
        self.assertTrue(kb.get_sfr(0xA8) & 0x80, "EA must be on")
        kb.brk(0x0000)
        kb.brk(kb._a("systick_interrupt_handler"))
        for n in range(max_isr):
            if kb.stopped_at(kb.run()) == 0x0000:
                kb.cmd("delete")
                return n, "WATCHDOG" in kb.stderr_text()
        kb.cmd("delete")
        return None, "WATCHDOG" in kb.stderr_text()

    def test_main_loop_hang_is_reset(self):
        n, logged = self.hang_and_count(hang=True)
        self.assertIsNotNone(n, "no watchdog reset within 4000 scans of a hung main loop")
        self.assertTrue(logged)

    def test_running_main_loop_is_not_reset(self):
        n, logged = self.hang_and_count(hang=False)
        self.assertIsNone(n, "the watchdog reset a running main loop after %s scans" % n)
        self.assertFalse(logged)


class TestWatchdogKickGap(Case):
    """The longest stretch between watchdog kicks in normal running stays near
    build-8's (about 2 ms), when the Timer2 scan still kicked it: at most 3 ms
    at 24 MHz, with the LEDs animating (the default effect redraws every ~130
    scans). The real watchdog period is not known. The simulator logs each gap
    of 1 ms or more ("[SIE] WDTGAP <cycles> ..."); the delays run for real
    once the main loop is reached."""

    LIMIT_CYCLES = 3 * 24000
    ISRS = 600

    def gaps(self, kb, since):
        return [int(n) for n in re.findall(r"\[SIE\] WDTGAP (\d+) ", kb.stderr_text()[since:])]

    def run_isrs(self, kb, n):
        isr, rr = kb._a("systick_interrupt_handler"), kb._a("user_matrix_read_rows")
        kb.brk(isr)
        kb.brk(rr)
        seen = 0
        while seen < n:
            if kb.stopped_at(kb.run()) == isr:
                seen += 1
            else:
                kb.matrix.inject(kb)
        kb.cmd("delete")

    def check(self, usb, key=None):
        kb = FixSim(self.FIRMWARE)
        self.addCleanup(kb.close)
        kb.boot(usb=usb, mac=False)
        if usb:
            kb.mark_usb_configured()
        self.assertIn("[SIE] WDT armed", kb.stderr_text(), "simulator without the kick-gap log (tools/ucsim)")
        kb.restore_rom("delay_us")
        kb.restore_rom("delay_ms")
        since = len(kb.stderr_text())
        if key:
            kb.matrix.press(*key)
        self.run_isrs(kb, self.ISRS)
        gaps = self.gaps(kb, since)
        worst = max(gaps, default=0)
        self.assertLessEqual(worst, self.LIMIT_CYCLES,
                             "longest gap between watchdog kicks %d cycles (%.1f ms)" % (worst, worst / 24000))

    def test_usb_idle_with_the_leds_animating(self):
        self.check(usb=True)

    def test_wireless_idle_with_the_leds_animating(self):
        self.check(usb=False)

    def test_wireless_key_held_without_ack(self):
        self.check(usb=False, key=KEY["A"])


class TestUsbBootRadio(Case):
    """At a boot in the USB position the radio ends up told USB mode
    (aa 03 06 01, as on a slider change to USB), not linked to Bluetooth 1."""

    def boot_frames(self, usb):
        kb = FixSim(self.FIRMWARE)
        self.addCleanup(kb.close)
        kb.reset_fast(p5=0xFF if usb else 0xFF & ~0x20)
        xfer, buf, stop = kb._a("bb_spi_xfer"), kb._a("rf_tx_buf"), kb._a("kb_update_switches")
        kb.brk(xfer)
        kb.brk(stop)
        frames = []
        for _ in range(400):
            if kb.stopped_at(kb.run()) == stop:
                break
            frames.append(kb.get_xram(buf, 6))
        kb.cmd("delete")
        # the link commands only: 01 = link / pairing, 06 = USB mode
        return [f[:5] for f in frames if f[:3] in ([0xAA, 0x03, 0x01], [0xAA, 0x03, 0x06])]

    def test_usb_boot_ends_in_usb_mode(self):
        link = self.boot_frames(usb=True)
        self.assertTrue(link, "no link command at all")
        self.assertEqual(link[-1], [0xAA, 0x03, 0x06, 0x01, 0x00], "last link command: %s" % link)
        self.assertNotIn([0xAA, 0x03, 0x01, 0x00, 0x01], link, "Bluetooth 1 must not be linked")

    def test_wireless_boot_links_the_saved_slot(self):
        link = self.boot_frames(usb=False)
        self.assertEqual(link[-1], [0xAA, 0x03, 0x01, 0x00, 0x01], "last link command: %s" % link)
        self.assertNotIn([0xAA, 0x03, 0x06, 0x01, 0x00], link)


class TestRemoteWakeup(Case):
    """USB suspend on the Air75 powers the MCU down (POWERDOWN_KEEP_USB_ALIVE).
    A key waking it may signal resume (USBCON.WKUP) only if the host enabled
    remote wakeup and the bus is still suspended; RESMIF (the host resuming the
    bus) ends the suspend. The host's side goes through the USB interface:
    SET/CLEAR_FEATURE(DEVICE_REMOTE_WAKEUP) as SETUP packets on EP0 (checked
    with GET_STATUS), and SUSPIF / RESMIF through usb_irq_dispatch()."""

    def enumerated_session(self, remote_wakeup):
        kb = self.session(usb=True)
        kb.skip_power_down()
        self.run_scans(kb, 64)
        kb.setup_packet(SET_FEATURE_REMOTE_WAKEUP)
        if not remote_wakeup:
            kb.setup_packet(CLEAR_FEATURE_REMOTE_WAKEUP)
        before = len(kb.ep0_in())
        kb.setup_packet(GET_STATUS_DEVICE)
        status = kb.ep0_in()[before:]
        self.assertTrue(status, "no GET_STATUS reply")
        self.assertEqual(status[0][0] & 0x02, 0x02 if remote_wakeup else 0,
                         "GET_STATUS remote-wakeup bit: %s" % status)
        return kb

    def suspend(self, kb):
        """Stop at kb_update and dispatch SUSPIF there; the next main-loop
        pass's sleep_task() powers down."""
        kb.brk(kb._a("kb_update"))
        kb.run()
        kb.cmd("delete")
        self.dispatch(kb, SUSPIF, kb._a("kb_update"))
        self.assertEqual(iram_bit(kb, kb.bit_symbol("usb", "usb_suspended")), 1, "SUSPIF did not suspend")

    def wake(self, kb, key=True, host_resumed=False):
        """Run into the power-down; at the wake, a key (INT4) and/or the host's
        resume; return USBCON after the resume path."""
        restart = kb._a("clock_wake_restart")
        kb.brk(restart)
        self.assertEqual(kb.stopped_at(kb.run()), restart, "no power-down")
        kb.cmd("delete")
        if key:
            kb.cmd("set mem xram 0x%x 0x01" % kb._xdata_static("power", "int4_woke"))
        if host_resumed:
            self.dispatch(kb, RESMIF, restart)
        kb.brk(kb._a("user_sleep_wake"))
        kb.run()
        kb.cmd("delete")
        return kb.get_sfr(USBCON)

    @staticmethod
    def dispatch(kb, flags, resume_pc):
        """Run usb_irq_dispatch() once with these USBIF1 flags, with interrupts
        off, then carry on at resume_pc (the simulator raises the USB vector
        only for SETUP)."""
        ie = kb.get_sfr(0xA8)
        kb.set_sfr(0xA8, ie & 0x7F)
        kb.set_sfr(USBIF1, flags)
        kb.call("usb_irq_dispatch", resume_pc=resume_pc)
        kb.set_sfr(0xA8, ie)

    def test_no_wkup_when_the_host_disabled_remote_wakeup(self):
        kb = self.enumerated_session(remote_wakeup=False)
        self.suspend(kb)
        self.assertEqual(self.wake(kb) & WKUP, 0, "USBCON.WKUP set without the host's permission")

    def test_wkup_when_the_host_enabled_remote_wakeup(self):
        kb = self.enumerated_session(remote_wakeup=True)
        self.suspend(kb)
        self.assertEqual(self.wake(kb) & WKUP, WKUP)

    def test_no_wkup_when_the_host_resumed_the_bus(self):
        kb = self.enumerated_session(remote_wakeup=True)
        self.suspend(kb)
        self.assertEqual(self.wake(kb, key=True, host_resumed=True) & WKUP, 0,
                         "resume signalled on top of the host's resume")

    def test_resmif_ends_the_suspend(self):
        """SUSPIF then RESMIF with no main-loop pass between (a pass would
        power down, and the resume path clears the flag by itself)."""
        kb = self.enumerated_session(remote_wakeup=True)
        self.suspend(kb)
        self.dispatch(kb, RESMIF, kb._a("kb_update"))
        self.assertEqual(iram_bit(kb, kb.bit_symbol("usb", "usb_suspended")), 0,
                         "usb_suspended still set after RESMIF")


if __name__ == "__main__":
    unittest.main()
