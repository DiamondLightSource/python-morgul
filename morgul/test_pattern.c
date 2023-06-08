#include <stdio.h>
#include <stdlib.h>

unsigned int *in;
unsigned int *out;

void setup() {
  in = (unsigned int *)malloc(sizeof(unsigned int) * 512 * 1024);
  out = (unsigned int *)malloc(sizeof(unsigned int) * (512 + 2) * (1024 + 6));

  // fill in test pattern
  for (int i = 0, k = 0; i < 512; i++) {
    for (int j = 0; j < 1024; j++, k++) {
      in[k] = 1;
    }
  }

  // double some pixels - horizontal
  for (int j = 0; j < 1024; j++) {
    in[255 * 1024 + j] *= 2;
    in[256 * 1024 + j] *= 2;
  }

  // double some pixels - vertical
  for (int j = 0; j < 512; j++) {
    in[j * 1024 + 255] *= 2;
    in[j * 1024 + 256] *= 2;
    in[j * 1024 + 511] *= 2;
    in[j * 1024 + 512] *= 2;
    in[j * 1024 + 767] *= 2;
    in[j * 1024 + 768] *= 2;
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
      (unsigned int *)malloc(514 * 1024 * sizeof(unsigned int));

  // copy the simple bits in -> out
  for (int i = 1; i < 255; i++) {
    for (int j = 1; j < 255; j++) {
      out[i * 1030 + j] = in[i * 1024 + j];
      out[i * 1030 + j + 258] = in[i * 1024 + j + 256];
      out[i * 1030 + j + 516] = in[i * 1024 + j + 512];
      out[i * 1030 + j + 774] = in[i * 1024 + j + 768];
      out[i * 1030 + j + 265740] = in[i * 1024 + j + 262144];
      out[i * 1030 + j + 258 + 265740] = in[i * 1024 + j + 256 + 262144];
      out[i * 1030 + j + 516 + 265740] = in[i * 1024 + j + 512 + 262144];
      out[i * 1030 + j + 774 + 265740] = in[i * 1024 + j + 768 + 262144];
    }
  }

  // straight copy column 0, 1023 - outside of the to-be-doubled regions
  for (int i = 0; i < 255; i++) {
    // top half
    out[i * 1030] = in[i * 1024];
    out[i * 1030 + 1029] = in[i * 1024 + 1023];
    // bottom half
    out[(i + 258) * 1030] = in[(i + 257) * 1024];
    out[(i + 258) * 1030 + 1029] = in[(i + 257) * 1024 + 1023];
  }

  // straight copy row 0, 511
  for (int j = 1; j < 255; j++) {
    // top half
    out[j] = in[j];
    out[j + 258] = in[j + 256];
    out[j + 516] = in[j + 512];
    out[j + 774] = in[j + 786];
    out[j + 1030 * 513] = in[j + 511 * 1024];
    out[j + 258 + 1030 * 513] = in[j + 256 + 511 * 1024];
    out[j + 516 + 1030 * 513] = in[j + 512 + 511 * 1024];
    out[j + 774 + 1030 * 513] = in[j + 786 + 511 * 1024];
  }

  // then split pixels - horizontal band - in -> work

  // then split pixels - vertical band - work -> out

  free(work);
}

int main(int argc, char **argv) {
  setup();

  FILE *fout = fopen("test_pattern.dat", "wb");
  for (int i = 0, k = 0; i < 514; i++) {
    for (int j = 0; j < 1030; j++, k++) {
      out[i * 1030 + j] = 0;
    }
  }
  embiggen(in, out);
  fwrite(out, sizeof(unsigned int), 514 * 1030, fout);
  fclose(fout);

  teardown();
  return 0;
}