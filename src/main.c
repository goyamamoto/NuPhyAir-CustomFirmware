#include "reset.h"
#include "clock.h"
#include "peripherals.h"
#include "ldo.h"
#include "watchdog.h"
#include "interrupts.h"
#include "usb.h"
#include "debug.h"
#include "console.h"
#include "matrix.h"
#include "utils.h"
#include "keyboard.h"
#include "user_init.h"
#include "indicators.h"
#include "kb.h"
#include "settings.h"
#include "tick.h"
#include "sleep.h"
#include "diag.h"
#ifdef DEBUG_SINK_UART
#    include "uart.h"
#endif
#ifdef RF_ENABLED
#    include "rf_controller.h"
#endif
void init(void)
{
    reset_init();
    ldo_init();
    clock_init();
#ifdef BOOT_ESCAPE
    // Before anything else can hang: a board-defined key held at power-up jumps
    // to the ISP bootloader. It needs the clock already up.
    user_boot_escape();
#endif
    peripherals_init();
#ifdef DEBUG_SINK_UART
    uart_init();
#endif

    user_init();

    matrix_init();
    keyboard_init();
    usb_init();
    indicators_init();

    tick_init();

    EA = 1;
}

static void restore_settings(void)
{
    if (!settings_load()) {
        indicators_apply_defaults();
    }
    indicators_validate_settings();
}

#ifdef RF_ENABLED
static void restore_rf_link(void)
{
#ifdef RF_USB_MODE_AT_BOOT
    // Booted with the slider on USB: tell the radio USB mode, as a slider
    // change to USB does, instead of linking it to the saved slot (a bonded
    // host would stay connected while the keyboard types over USB).
    if (kb_conn_mode_is_usb()) {
        rf_apply_usb_mode();
    } else {
        rf_set_link((rf_mode_t)user_settings.rf_link);
    }
#else
    rf_set_link((rf_mode_t)user_settings.rf_link);
#endif

    keyboard_state.rf_link   = user_settings.rf_link;
    keyboard_state.connected = 1;
    keyboard_state.paired    = 1;
}
#endif

void main(void)
{
    init();

    dprintf("SMK v" TOSTRING(SMK_VERSION) "\r\n");
    dprintf("KB " KEYBOARD_NAME " / " LAYOUT_NAME "\r\n");
    dprintf("DEVICE vId:" TOSTRING(USB_VID) " pId:" TOSTRING(USB_PID) "\n\r");

    kb_init();

#ifdef RF_ENABLED
    rf_init();
#endif

    restore_settings();
#if DEBUG == 1
    settings_dump();
#endif

    usb_wait_for_enumeration();
    indicators_start();

#ifdef RF_ENABLED
    restore_rf_link();
#endif

    sleep_init(); // needs the board's GPIO and RF up

    while (1) {
        watchdog_kick();

        kb_update_switches();
        kb_update();
        matrix_task();

        indicators_render();

        usb_task();
        settings_task();
        sleep_task();

#if DEBUG == 1
        diag_task();
        interrupts_task();
        console_task();
#endif
    }
}
