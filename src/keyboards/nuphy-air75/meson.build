kb_dir = meson.current_source_dir()

keyboards += {
    'nuphy-air75' : {
        'dir' : kb_dir,
        'platform' : 'sh68f90',
        'src' : files(
            'user_matrix.c',
            'user_init.c',
            'user_sleep.c',
            'kb.c',
            'indicators.c',
        ),
        'layouts' : {
            # Plain US ANSI.
            'ansi' : {
                'dir' : kb_dir / 'layouts/ansi',
                'src' : files('layouts/ansi/layout.c'),
            },
            # ANSI plus US-JIS (Fn+Tab), IME mod-taps beside Space and Caps Lock / Left Ctrl swapped.
            'usjis' : {
                'dir' : kb_dir / 'layouts/usjis',
                'src' : files('layouts/usjis/layout.c'),
                'defines' : ['USJIS=1', 'TAP_HOLD=1'],
            },
        },
        'options' : {
            'vendor_id' : '0x05ac',
            'product_id' : '0x024f',
            'wireless' : 'bk3632',
            'defines' : [
                'BOOT_ESCAPE=1',
                'APPLE_FN=1',
                'RF_BT_NAME="Air75"',
                # A key goes up with the keycode it went down with, and Fn-up sends
                # the report for the keys it clears (src/smk/matrix.c).
                'LATCH_KEYCODES=1',
                # Radio: a retry after a missed ACK resends the frame, and a
                # consumer/system report is sent again until ACKed (bk3632).
                'BK3632_TX_KEEPS_FRAME=1',
                'BK3632_EXTRA_PENDING=1',
                # The Timer2 matrix scan does not kick the watchdog, so a hung
                # main loop is reset (src/sino51lib/delay.c, src/smk/matrix.c).
                'SCAN_DELAY_NO_WDT_KICK=1',
                # A boot in the USB position tells the radio USB mode (src/main.c).
                'RF_USB_MODE_AT_BOOT=1',
                # USBCON.WKUP only with the host's permission; RESMIF ends the
                # suspend (src/smk/usb.c, src/sino51lib/sh68f90/power.c).
                'USB_REMOTE_WAKEUP_STRICT=1',
            ],
            'manufacturer' : 'SMK',
            'product' : 'Air75 (SMK)',
            'led_rows' : '6',
            'led_cols' : '16',
            'led_cx2' : '15',
            'led_cy2' : '5',
        },
    },
}
