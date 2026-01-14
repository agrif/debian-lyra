// helper to paste together rm_io0_func labels
#define _RM_IO(pin, func) rm_io ## pin ## _ ## func
#define RM_IO(pin, func) _RM_IO(pin, func)
