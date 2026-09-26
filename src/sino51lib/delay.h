#pragma once

#include <stdint.h>

void delay_ms(uint16_t cnt);
void delay_us(uint16_t cnt);

#ifdef SCAN_DELAY_NO_WDT_KICK
// delay_us() without its watchdog kick, for interrupt handlers (the matrix scan).
void delay_us_no_kick(uint16_t cnt);
#endif
