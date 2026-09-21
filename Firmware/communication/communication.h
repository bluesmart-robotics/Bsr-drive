#ifndef COMMANDS_H
#define COMMANDS_H

// TODO: resolve assert
#define assert(expr)

#ifdef __cplusplus

#include <functional>
#include <limits>

extern "C" {
#endif

#include <cmsis_os.h>

void init_communication(void);
void start_uart_servers(void); // BSR v3.7: called separately from main.cpp, after motor setup

#ifdef __cplusplus
}
#endif

#endif /* COMMANDS_H */
