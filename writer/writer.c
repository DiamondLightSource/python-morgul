#include <hdf5.h>
#include <stdio.h>
#include <stdlib.h>

int bshuf_register_h5filter(void);

int main(void) {
  hid_t file_id, dset_id, fspace_id, mspace_id, dcpl_id;
  herr_t status;
  htri_t avail;
  unsigned int filter_config;
  int retval = 0;
  hsize_t chunk_dims[3] = {1, 512, 1024};
  hsize_t dset_dims[3] = {1024, 512, 1024};
  hsize_t mem_dims[3] = {1, 512, 1024};
  hsize_t start[3] = {0, 0, 0};
  hsize_t count[3] = {1, 1, 1};
  hsize_t block[3] = {1, 512, 1024};

  // register plugin
  if (bshuf_register_h5filter() < 0) {
    fprintf(stderr, "Error calling plugin register\n");
    return 1;
  }

  int *buffer = (int *)malloc(sizeof(int) * 512 * 1024);

  // fill buffer with very easily compressed data
  for (int j = 0; j < 512 * 1024; j++)
    buffer[j] = j % 8;

  file_id = H5Fcreate("out.h5", H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT);

  if (file_id < 0) {
    fprintf(stderr, "Error creating file\n");
    goto bork_file;
  }

  dcpl_id = H5Pcreate(H5P_DATASET_CREATE);

  if (dcpl_id < 0) {
    fprintf(stderr, "Error creating dcpl\n");
    goto bork_dcpl;
  }

  const unsigned int zargs[2] = {0, 2};
  status = H5Pset_filter(dcpl_id, 32008, H5Z_FLAG_MANDATORY, 2, zargs);

  if (status < 0) {
    fprintf(stderr, "Error setting filter\n");
    goto bork_dcpl;
  }

  avail = H5Zfilter_avail(32008);

  if (!avail) {
    fprintf(stderr, "Filter not available\n");
    goto bork_dcpl;
  }

  if (avail) {
    status = H5Zget_filter_info(32008, &filter_config);
    if (status < 0) {
      fprintf(stderr, "Error getting filter info\n");
      goto bork_dcpl;
    }
    if (!(filter_config & H5Z_FILTER_CONFIG_ENCODE_ENABLED)) {
      fprintf(stderr, "Filter not available for encode\n");
      goto bork_dcpl;
    }
  }

  status = H5Pset_chunk(dcpl_id, 3, chunk_dims);

  if (status < 0) {
    fprintf(stderr, "Error setting chunk\n");
    goto bork_dcpl;
  }

  fspace_id = H5Screate_simple(3, dset_dims, NULL);

  if (fspace_id < 0) {
    fprintf(stderr, "Error creating fspace\n");
    goto bork_fspace;
  }

  dset_id = H5Dcreate(file_id, "data", H5T_NATIVE_UINT, fspace_id, H5P_DEFAULT,
                      dcpl_id, H5P_DEFAULT);

  if (dset_id < 0) {
    fprintf(stderr, "Error creating dset\n");
    goto bork_dset;
  }

  mspace_id = H5Screate_simple(3, mem_dims, NULL);

  if (mspace_id < 0) {
    fprintf(stderr, "Error creating mspace\n");
    goto bork_mspace;
  }

  for (int j = 0; j < 1024; j++) {
    start[0] = j;
    status = H5Sselect_hyperslab(fspace_id, H5S_SELECT_SET, start, NULL, count,
                                 block);
    if (status < 0) {
      fprintf(stderr, "Error selecting frame %d\n", j);
      goto bork_write;
    }
    status = H5Dwrite(dset_id, H5T_NATIVE_UINT, mspace_id, fspace_id,
                      H5P_DEFAULT, buffer);
    if (status < 0) {
      fprintf(stderr, "Error writing frame %d\n", j);
      goto bork_write;
    }
  }

bork_write:
  H5Sclose(mspace_id);
bork_mspace:
  H5Dclose(dset_id);
bork_dset:
  H5Sclose(fspace_id);
bork_fspace:
  H5Pclose(dcpl_id);
bork_dcpl:
  H5Fclose(file_id);
bork_file:
  return retval;
}
