
cmake_minimum_required(VERSION 3.20)
project(writer LANGUAGES C)

find_package(HDF5 REQUIRED)

add_library(bitshuffle STATIC 
    bitshuffle/lz4/lz4.c
    bitshuffle/src/bitshuffle.c
    bitshuffle/src/bshuf_h5plugin.c
    bitshuffle/src/iochain.c
    bitshuffle/src/bshuf_h5filter.c
    bitshuffle/src/bitshuffle_core.c
)
target_include_directories(bitshuffle PUBLIC bitshuffle/lz4)

add_executable(writer writer.c)
target_link_libraries(writer PRIVATE bitshuffle hdf5::hdf5)