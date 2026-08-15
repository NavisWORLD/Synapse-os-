#include "synapse/synapse.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET synapse_socket_t;
#define SYNAPSE_INVALID_SOCKET INVALID_SOCKET
static int synapse_socket_init(void) {
    static int initialized = 0;
    if (initialized) return 1;
    WSADATA data;
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0) return 0;
    initialized = 1;
    return 1;
}
static void synapse_close_socket(synapse_socket_t fd) { closesocket(fd); }
static int synapse_set_nonblocking(synapse_socket_t fd) {
    u_long mode = 1;
    return ioctlsocket(fd, FIONBIO, &mode) == 0;
}
static int synapse_connect_in_progress(void) {
    int e = WSAGetLastError();
    return e == WSAEWOULDBLOCK || e == WSAEINPROGRESS || e == WSAEINVAL;
}
#else
#include <fcntl.h>
#include <netdb.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>
typedef int synapse_socket_t;
#define SYNAPSE_INVALID_SOCKET (-1)
static int synapse_socket_init(void) { return 1; }
static void synapse_close_socket(synapse_socket_t fd) { close(fd); }
static int synapse_set_nonblocking(synapse_socket_t fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    return flags >= 0 && fcntl(fd, F_SETFL, flags | O_NONBLOCK) == 0;
}
static int synapse_connect_in_progress(void) { return errno == EINPROGRESS || errno == EWOULDBLOCK; }
#endif

uint32_t synapse_abi_version(void) { return 1u; }

const char *synapse_result_string(int result) {
    switch (result) {
        case SYNAPSE_OK: return "ok";
        case SYNAPSE_EINVAL: return "invalid argument";
        case SYNAPSE_ENOENT: return "not found";
        case SYNAPSE_EIO: return "I/O error";
        case SYNAPSE_EBUFFER: return "buffer too small";
        case SYNAPSE_ENET: return "network error";
        default: return "unknown error";
    }
}

int synapse_status_read(const char *path, char *buffer, size_t capacity, size_t *required) {
    if (!path || !*path || !required) return SYNAPSE_EINVAL;
    FILE *f = fopen(path, "rb");
    if (!f) return errno == ENOENT ? SYNAPSE_ENOENT : SYNAPSE_EIO;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return SYNAPSE_EIO; }
    long length = ftell(f);
    if (length < 0) { fclose(f); return SYNAPSE_EIO; }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return SYNAPSE_EIO; }
    size_t need = (size_t)length + 1u;
    *required = need;
    if (!buffer || capacity == 0) { fclose(f); return SYNAPSE_OK; }
    if (capacity < need) { fclose(f); return SYNAPSE_EBUFFER; }
    size_t got = fread(buffer, 1, (size_t)length, f);
    if (got != (size_t)length || ferror(f)) { fclose(f); return SYNAPSE_EIO; }
    buffer[got] = '\0';
    if (fclose(f) != 0) return SYNAPSE_EIO;
    return SYNAPSE_OK;
}

static int synapse_wait_connected(synapse_socket_t fd, uint32_t timeout_ms) {
    fd_set writefds;
    FD_ZERO(&writefds);
    FD_SET(fd, &writefds);
    struct timeval timeout;
    timeout.tv_sec = (long)(timeout_ms / 1000u);
    timeout.tv_usec = (long)((timeout_ms % 1000u) * 1000u);
#ifdef _WIN32
    int ready = select(0, NULL, &writefds, NULL, &timeout);
#else
    int ready = select(fd + 1, NULL, &writefds, NULL, &timeout);
#endif
    if (ready <= 0) return 0;
    int error = 0;
#ifdef _WIN32
    int len = (int)sizeof(error);
#else
    socklen_t len = (socklen_t)sizeof(error);
#endif
    if (getsockopt(fd, SOL_SOCKET, SO_ERROR, (char *)&error, &len) != 0) return 0;
    return error == 0;
}

int synapse_service_reachable(const char *host, uint16_t port, uint32_t timeout_ms) {
    if (!host || !*host || port == 0u) return 0;
    if (!synapse_socket_init()) return 0;

    char service[6];
    int written = snprintf(service, sizeof(service), "%u", (unsigned)port);
    if (written <= 0 || (size_t)written >= sizeof(service)) return 0;

    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_protocol = IPPROTO_TCP;

    struct addrinfo *results = NULL;
    if (getaddrinfo(host, service, &hints, &results) != 0) return 0;

    int reachable = 0;
    for (struct addrinfo *it = results; it != NULL && !reachable; it = it->ai_next) {
        synapse_socket_t fd = socket(it->ai_family, it->ai_socktype, it->ai_protocol);
        if (fd == SYNAPSE_INVALID_SOCKET) continue;
        if (!synapse_set_nonblocking(fd)) { synapse_close_socket(fd); continue; }
        int rc = connect(fd, it->ai_addr, (int)it->ai_addrlen);
        if (rc == 0) {
            reachable = 1;
        } else if (synapse_connect_in_progress()) {
            reachable = synapse_wait_connected(fd, timeout_ms);
        }
        synapse_close_socket(fd);
    }
    freeaddrinfo(results);
    return reachable;
}
