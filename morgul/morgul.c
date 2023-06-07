/* morgul
 *
 * Tool to correct raw Jungfrau data from a *single module* as -
 *
 *  - e(keV) = (I(ADU) - P(ADU)) / G(ADU/keV)
 *  - I(photons) = e(keV) / photon energy
 *
 *  1st cut working against a specific data set from PSI -> makes a
 *  lot of assumptions in particular:
 *
 *  - first 1,000 frames are manually driven low gain (G2) pedestal values
 *  - second 1,000 frames are manually driven medium gain (G1) pedestals
 *  - next 1,000 frames are *not* manually driven so represent high gain (G0)
 *    pedestal values
 *
 *  Also assumes that the gain correction tables are passed as input
 *  and consist of float64_t values of 512x1024 pixels for gain modes
 *  0, 1, 2 *in that order*
 *
 *  Usage:
 *
 *  morgul gain.dat data0 data1 ... dataN
 *
 *  This version also assumes that the data are saved as raw / unformatted
 *  data with 48 byte header (assumed to contain nonsense) followed by little
 *  endian uint16_t which are the 2-bit gain mode in MSB followed by 14 bits
 *  ADC readout which we will be processing.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

double *g0 = NULL;
double *g1 = NULL;
double *g2 = NULL;
double *p0 = NULL;
double *p1 = NULL;
double *p2 = NULL;

int *mask = NULL;

#define NY 512
#define NX 1024

void setup(char *filename) {
  FILE *fin = fopen(filename, "rb");

  g0 = (double *)malloc(NY * NX * sizeof(double));
  g1 = (double *)malloc(NY * NX * sizeof(double));
  g2 = (double *)malloc(NY * NX * sizeof(double));

  fread((void *)g0, sizeof(double), NY * NX, fin);
  fread((void *)g1, sizeof(double), NY * NX, fin);
  fread((void *)g2, sizeof(double), NY * NX, fin);

  fclose(fin);
}

void pedestal(char *filename) {
  FILE *fin = fopen(filename, "rb");

  p0 = (double *)malloc(NY * NX * sizeof(double));
  p1 = (double *)malloc(NY * NX * sizeof(double));
  p2 = (double *)malloc(NY * NX * sizeof(double));

  mask = (int *)malloc(NY * NX * sizeof(int));

  // clear arrays yes I could just use memset or calloc even
  for (int p = 0; p < NY * NX; p++) {
    p0[p] = p1[p] = p2[p] = 0.0;
    mask[p] = 1;
  }

  unsigned short *pixels =
      (unsigned short *)malloc(NY * NX * sizeof(unsigned short));

  // low gain for 1000 frames

  for (int i = 0; i < 1000; i++) {
    uint16_t low = 0x3fff;
    fseek(fin, 48, SEEK_CUR);
    fread((void *)pixels, sizeof(unsigned short), NY * NX, fin);
    for (int p = 0; p < NY * NX; p++) {
      p2[p] += (double)(pixels[p] & low);
    }
  }

  for (int p = 0; p < NY * NX; p++) {
    p2[p] /= 1000;
  }

  // medium gain for 1000 frames

  for (int i = 0; i < 1000; i++) {
    uint16_t low = 0x3fff;
    fseek(fin, 48, SEEK_CUR);
    fread((void *)pixels, sizeof(unsigned short), NY * NX, fin);
    for (int p = 0; p < NY * NX; p++) {
      p1[p] += (double)(pixels[p] & low);
    }
  }

  for (int p = 0; p < NY * NX; p++) {
    p1[p] /= 1000;
  }

  // high gain for 1000 frames *unless* gain bits set
  // in which case mask

  for (int i = 0; i < 1000; i++) {
    uint16_t high = 0xc000;
    fseek(fin, 48, SEEK_CUR);
    fread((void *)pixels, sizeof(unsigned short), NY * NX, fin);
    for (int p = 0; p < NY * NX; p++) {
      if (pixels[p] & high) {
        mask[p] = 0;
        p0[p] = 0;
      } else {
        p0[p] += (double)pixels[p];
      }
    }
  }

  for (int p = 0; p < NY * NX; p++) {
    p0[p] /= 1000;
  }

  free(pixels);
}

void work(char *filename) {
  FILE *fin = fopen(filename, "rb");

  unsigned short *pixels =
      (unsigned short *)malloc(NY * NX * sizeof(unsigned short));

  unsigned int *output = (unsigned int *)malloc(NY * NX * sizeof(unsigned int));

  // skip warmup frames

  for (int i = 0; i < 2000; i++) {
    fseek(fin, 48 + NY * NX * sizeof(unsigned short), SEEK_CUR);
  }

  // now start to do some calculations

  for (int i = 2000; i < 10000; i++) {
    uint16_t low = 0x3fff;
    fseek(fin, 48, SEEK_CUR);
    fread((void *)pixels, sizeof(unsigned short), NY * NX, fin);
    for (int p = 0; p < NY * NX; p++) {
      pixels[p] *= mask[p];

      int mode = pixels[p] >> 14;

      double pixel = (double)(pixels[p] & low);

      switch (mode) {
      case 3:
        output[p] = (pixel - p2[p]) / g2[p];
        break;
      case 1:
        output[p] = (pixel - p1[p]) / g1[p];
        break;
      default:
        output[p] = (pixel - p0[p]) / g0[p];
        break;
      }

      if (mask[p] == 0) {
        output[p] = 0xffffffff;
      }
    }

    char result[100];
    sprintf(result, "frame_%05d.raw", i);
    FILE *fout = fopen(result, "wb");
    fwrite(output, sizeof(unsigned int), NY * NX, fout);
    fclose(fout);
    printf("Wrote %s\n", result);
  }

  free(output);
  free(pixels);
}

void teardown(void) {
  free(g0);
  free(g1);
  free(g2);
  free(p0);
  free(p1);
  free(p2);
  free(mask);
}

int main(int argc, char **argv) {
  if (argc < 3) {
    fprintf(stderr, "%s gain data\n", argv[0]);
    return 1;
  }

  char *gain = argv[1];
  char *data = argv[2];

  setup(gain);
  pedestal(data);
  work(data);

  teardown();

  return 0;
}