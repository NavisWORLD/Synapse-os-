#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "synapse/synapse.h"

int main(void) {
    assert(synapse_abi_version() == 1u);
    const char *path = "/tmp/synapse-abi-test.json";
    FILE *f = fopen(path, "wb");
    assert(f != NULL);
    const char *payload = "{\"ok\":true}";
    assert(fwrite(payload, 1, strlen(payload), f) == strlen(payload));
    assert(fclose(f) == 0);

    size_t needed = 0;
    assert(synapse_status_read(path, NULL, 0, &needed) == SYNAPSE_OK);
    assert(needed == strlen(payload) + 1);

    char tiny[2];
    assert(synapse_status_read(path, tiny, sizeof tiny, &needed) == SYNAPSE_EBUFFER);

    char *buf = calloc(needed, 1);
    assert(buf != NULL);
    assert(synapse_status_read(path, buf, needed, &needed) == SYNAPSE_OK);
    assert(strcmp(buf, payload) == 0);
    free(buf);

    assert(synapse_status_read("/tmp/definitely-missing-synapse.json", NULL, 0, &needed) == SYNAPSE_ENOENT);
    assert(synapse_service_reachable("127.0.0.1", 65534, 10) == 0);
    remove(path);
    return 0;
}
