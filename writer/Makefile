BSHUF_SRC = bitshuffle/lz4/lz4.c \
	bitshuffle/src/bitshuffle.c \
	bitshuffle/src/bshuf_h5plugin.c \
	bitshuffle/src/iochain.c \
	bitshuffle/src/bshuf_h5filter.c \
	bitshuffle/src/bitshuffle_core.c

BSHUF_OBJ = bitshuffle/lz4/lz4.o \
	bitshuffle/src/bshuf_h5plugin.o \
	bitshuffle/src/bitshuffle.o \
	bitshuffle/src/iochain.o \
	bitshuffle/src/bshuf_h5filter.o \
	bitshuffle/src/bitshuffle_core.o

CFLAGS = -O2 -Wall -Ofast

%.o : %.c
	h5cc -c $(CFLAGS) $< -o $@

writer.exe:	writer.o libbshuf.a
	h5cc -o writer.exe writer.o -L. -lbshuf

libbshuf.a: $(BSHUF_OBJ)
	ar -r libbshuf.a $(BSHUF_OBJ)