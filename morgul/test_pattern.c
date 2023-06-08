#include <stdio.h>
#include <stdlib.h>

unsigned int *in;
unsigned int *out;

#define NY 512
#define NX 1024

void setup() {
  in = (unsigned int *)malloc(sizeof(unsigned int) * NY * NX);
  out = (unsigned int *)malloc(sizeof(unsigned int) * (NY + 2) * (NX + 6));

  // fill in test pattern
  for (int i = 0, k = 0; i < NY; i++) {
    for (int j = 0; j < NX; j++, k++) {
      in[k] = 1;
    }
  }

  // double some pixels - horizontal
  for (int j = 0; j < NX; j++) {
    in[255 * NX + j] *= 2;
    in[256 * NX + j] *= 2;
  }

  // double some pixels - vertical
  for (int j = 0; j < NY; j++) {
    in[j * NX + 255] *= 2;
    in[j * NX + 256] *= 2;
    in[j * NX + 511] *= 2;
    in[j * NX + 512] *= 2;
    in[j * NX + 767] *= 2;
    in[j * NX + 768] *= 2;
  }
}

void teardown() {
  free(in);
  free(out);
}

inline int coin() { return rand() & 0x1; }

// embiggen - unpack the double and quadro pixels to deal with the
// segments where the ASICs meet
void embiggen(unsigned int *in, unsigned int *out) {
  unsigned int *work =
      (unsigned int *)malloc(512 * 1030 * sizeof(unsigned int));
  free(work);
}

int main(int argc, char **argv) {
  setup();
  teardown();
  return 0;
}