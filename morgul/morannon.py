import configparser
import glob
import os
import sys

import numpy
import h5py

hostname = os.uname()[1]
install = os.path.dirname(os.path.realpath(__file__))


def get_config():
    """Get the local configuration from the installation directory"""
    configuration = configparser.ConfigParser()
    assert (
        "morannon.ini" in configuration.read(os.path.join(install, "morannon.ini"))[0]
    )
    return configuration


config = get_config()


def psi_gain_maps(detector):
    """Read gain maps from installed location, return as 3 x numpy array g0, g1, g2"""
    calib = config[hostname]["calibration"]
    result = {}
    for k in config.keys():
        if k.startswith(detector):
            module = config[k]["module"]
            gain_file = glob.glob(os.path.join(calib, f"M{module}_fullspeed", "*.bin"))
            assert len(gain_file) == 1
            shape = 3, 512, 1024
            count = shape[0] * shape[1] * shape[2]
            gains = numpy.fromfile(
                open(gain_file[0], "r"), dtype=numpy.float64, count=count
            ).reshape(*shape)
            result[f"M{module}"] = gains
    return result


def main(detector):
    maps = psi_gain_maps(detector)

    with h5py.File(f"{detector}_calib.h5", "w") as f:
        for k in sorted(maps):
            g = f.create_group(k)
            g012 = maps[k]
            for j in 0, 1, 2:
                g.create_dataset(f"g{j}", data=g012[j])


if __name__ == "__main__":
    detector = sys.argv[1]
    main(detector)
