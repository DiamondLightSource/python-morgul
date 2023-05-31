#include <hdf5.h>
#include <hdf5_hl.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

int main(int argc,
         char ** argv) {
  hid_t f, d, s;
  hsize_t dims[3], offset[3], size;

  f = H5Fopen(argv[1], H5F_ACC_RDONLY, H5P_DEFAULT);
  d = H5Dopen(f, "data", H5P_DEFAULT);
  s = H5Dget_space(d);

  H5Sget_simple_extent_dims(s, dims, NULL);

  int nn = dims[1] * dims[2];

  printf("%d dimension data set\n", H5Sget_simple_extent_ndims(s));

  for (int j = 0; j < 3; j++) {
    printf("n[%d] = %lld\n", j, dims[j]);
  }

  double* gain = (double *)malloc(sizeof(double) * nn);
  FILE * g = fopen(argv[2], "rb");
  fread(gain, sizeof(double), nn, g);
  fclose(g);

  // reciprocal gain more useful i.e. photons / ADU
  for (int j = 0; j < nn; j++) {
    if (gain[j] > 0) gain[j] = 1.0 / gain[j];
  }

  uint16_t* image = (uint16_t *)malloc(sizeof(uint16_t) * nn);
  uint32_t filter = 0;

  offset[1] = offset[2] = 0;

  uint16_t mode1 = 1 << 14;
  uint16_t mode2 = 1 << 15;

  double* sum_i = (double *)calloc(nn, sizeof(double));
  double* sum_i2 = (double *)calloc(nn, sizeof(double));

  for (int j = 0; j < dims[0]; j++) {
    offset[0] = j;
    H5Dget_chunk_storage_size(d, offset, &size);
    H5DOread_chunk(d, H5P_DEFAULT, offset, &filter, image);
    for (int k = 0; k < nn; k++) {
      if (image[k] & mode1) image[k] = 0;
      if (image[k] & mode2) image[k] = 0;
      sum_i[k] += gain[k] * image[k];
      sum_i2[k] += gain[k] * gain[k] * image[k] * image[k];
    }
  }

  double* mean = (double *)malloc(sizeof(double) * nn);
  double* stdev = (double *)malloc(sizeof(double) * nn);

  for (int j = 0; j < nn; j++) {
    mean[j] = sum_i[j] / dims[0];
    stdev[j] = sqrt((sum_i2[j] / dims[0]) - mean[j] * mean[j]);
  }

  FILE * v = fopen("variance.map", "wb");
  fwrite(stdev, sizeof(double), nn, v);
  fclose(v);

  free(stdev);
  free(mean);

  free(sum_i2);
  free(sum_i);

  free(gain);
  free(image);

  H5Dclose(d);
  H5Fclose(f);  
  return 0;
}