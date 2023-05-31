#include <hdf5.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc,
         char ** argv) {
  hid_t f, d, s;
  hsize_t dims[3];

  f = H5Fopen(argv[1], H5F_ACC_RDONLY, H5P_DEFAULT);
  d = H5Dopen(f, "data", H5P_DEFAULT);
  s = H5Dget_space(d);

  H5Sget_simple_extent_dims(s, dims, NULL);

  printf("%d dimension data set\n", H5Sget_simple_extent_ndims(s));

  for (int j = 0; j < 3; j++) {
    printf("n[%d] = %lld\n", j, dims[j]);
  }

  H5Dclose(d);
  H5Fclose(f);  
  return 0;
}