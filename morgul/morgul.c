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
 *  morgul energy (keV) gain.dat data0 data1 ... dataN
 *
 *  This version also assumes that the data are saved as raw / unformatted
 *  data with 48 byte header (assumed to contain nonsense) followed by little
 *  endian uint16_t which are the 2-bit gain mode in MSB followed by 14 bits
 *  ADC readout which we will be processing.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

double *g0 = NULL;
double *g1 = NULL;
double *g2 = NULL;
double *p0 = NULL;
double *p1 = NULL;
double *p2 = NULL;

double energy_keV = 0.0;

int *mask = NULL;

#define NY 512
#define NX 1024

// embiggen - unpack the central 254x254 pixel regions of each
// ASIC, everything else will be masked
void embiggen(unsigned int *in, unsigned int *out) {
  // set everything as MASK pattern
  memset(out, 0xff, 1030 * 514 * sizeof(unsigned int));

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
}

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

int work(char *filename, int skip, int offset) {

  struct stat finfo;

  // get the number of frames in the file based on the size in bytes
  stat(filename, &finfo);
  int nn = finfo.st_size / (48 + 2 * 512 * 1024);

  printf("%s -> %d frames\n", filename, nn);

  FILE *fin = fopen(filename, "rb");

  unsigned short *pixels =
      (unsigned short *)malloc(NY * NX * sizeof(unsigned short));

  unsigned int *scratch =
      (unsigned int *)malloc(NY * NX * sizeof(unsigned int));
  unsigned int *output =
      (unsigned int *)malloc(514 * 1030 * sizeof(unsigned int));

  // skip warmup frames if present

  for (int i = 0; i < skip; i++) {
    fseek(fin, 48 + NY * NX * sizeof(unsigned short), SEEK_CUR);
  }

  // now start to do some calculations

  for (int i = skip; i < nn; i++) {
    uint16_t low = 0x3fff;
    fseek(fin, 48, SEEK_CUR);
    fread((void *)pixels, sizeof(unsigned short), NY * NX, fin);
    for (int p = 0; p < NY * NX; p++) {
      pixels[p] *= mask[p];

      int mode = pixels[p] >> 14;

      double pixel = (double)(pixels[p] & low);

      switch (mode) {
      case 3:
        scratch[p] = (pixel - p2[p]) / (g2[p] * energy_keV);
        break;
      case 1:
        scratch[p] = (pixel - p1[p]) / (g1[p] * energy_keV);
        break;
      default:
        scratch[p] = (pixel - p0[p]) / (g0[p] * energy_keV);
        break;
      }

      if (mask[p] == 0) {
        scratch[p] = 0xffffffff;
      }
    }

    embiggen(scratch, output);

    char result[100];
    sprintf(result, "frame_%05d.raw", i - skip + offset);
    FILE *fout = fopen(result, "wb");
    fwrite(output, sizeof(unsigned int), 514 * 1030, fout);
    fclose(fout);
    printf("Wrote %s\n", result);
  }

  free(output);
  free(pixels);

  return nn - skip;
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
  if (argc < 4) {
    fprintf(stderr, "%s energy (keV) gain.dat data0 data1 .... dataN\n",
            argv[0]);
    return 1;
  }

  energy_keV = atof(argv[1]);
  char *gain = argv[2];
  char *data = argv[3];

  setup(gain);
  pedestal(data);

  int offset = 0;
  for (int j = 3; j < argc; j++) {
    data = argv[j];
    int skip = j == 3 ? 2000 : 0;
    offset += work(data, skip, offset);
  }

  teardown();

  return 0;
}