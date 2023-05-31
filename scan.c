#include <hdf5.h>
#include <hdf5_hl.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc,
         char ** argv) {
  hid_t f, d, s;
  hsize_t dims[3], offset[3], size;

  f = H5Fopen(argv[1], H5F_ACC_RDONLY, H5P_DEFAULT);
  d = H5Dopen(f, "data", H5P_DEFAULT);
  s = H5Dget_space(d);

  H5Sget_simple_extent_dims(s, dims, NULL);

  printf("%d dimension data set\n", H5Sget_simple_extent_ndims(s));

  for (int j = 0; j < 3; j++) {
    printf("n[%d] = %lld\n", j, dims[j]);
  }

  uint16_t* image = (uint16_t *)malloc(sizeof(uint16_t) * dims[1] * dims[2]);
  uint32_t filter = 0;

  offset[1] = offset[2] = 0;

  uint16_t mode1 = 1 << 14;
  uint16_t mode2 = 1 << 15;

  for (int j = 0; j < dims[0]; j++) {
    offset[0] = j;
    H5Dget_chunk_storage_size(d, offset, &size);
    H5DOread_chunk(d, H5P_DEFAULT, offset, &filter, image);
    int n1, n2;
    n1 = n2 = 0;
    for (int k = 0; k < dims[1] * dims[2]; k++) {
      if (image[k] & mode1) n1++;
      if (image[k] & mode2) n2++;
    }
    printf("%d %d %d\n", j, n1, n2);
  }

  free(image);

  H5Dclose(d);
  H5Fclose(f);  
  return 0;
}