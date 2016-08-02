import cffi

I = cffi.FFI()

I.set_source("asyncwatch.inotify",
"""
#include <sys/inotify.h>
""")

I.cdef("""
int inotify_init(void);int inotify_init1(int flags);
int inotify_add_watch(int fd, const char *pathname, uint32_t mask);
int inotify_rm_watch(int fd, int wd);
""")


if __name__ == '__main__':
    I.compile(verbose=True)
