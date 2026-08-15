#ifndef SYNAPSE_ABI_H
#define SYNAPSE_ABI_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32) && defined(SYNAPSE_ABI_BUILD_SHARED)
#  define SYNAPSE_API __declspec(dllexport)
#elif defined(_WIN32) && defined(SYNAPSE_ABI_USE_SHARED)
#  define SYNAPSE_API __declspec(dllimport)
#else
#  define SYNAPSE_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

enum synapse_result {
    SYNAPSE_OK = 0,
    SYNAPSE_EINVAL = 1,
    SYNAPSE_ENOENT = 2,
    SYNAPSE_EIO = 3,
    SYNAPSE_EBUFFER = 4,
    SYNAPSE_ENET = 5
};

SYNAPSE_API uint32_t synapse_abi_version(void);
SYNAPSE_API const char *synapse_result_string(int result);
SYNAPSE_API int synapse_status_read(const char *path, char *buffer, size_t capacity, size_t *required);
SYNAPSE_API int synapse_service_reachable(const char *host, uint16_t port, uint32_t timeout_ms);

#ifdef __cplusplus
}
#endif

#endif
