# Jungfrau Commissioning

Tools to assist with the commissioning effort, basic analysis etc.

## Calibration

Key calibration steps -

- finding noisy pixels from dark runs
- evaluation of run-time pedestal

Technically the second of these depends on the absence of spots, or signal, so will need some interactivity unless we know _a priori_ when the shutter was opened. Need to save the gain maps, mask into a data file for later access in the correction step.

## Corrections

Necessary corrections -

- identify dark region
- determine pedestal
- convert to photons, subtract pedestal, add constant, save to file with compression

This also requires the photon energy.

## MORGUL / MORANNON

Local equivalent of the JungfrauJoch system designed with simplicity in mind and potential for running automatically as a part of routine operation. Two main steps:

- `morannon`: creation of calibration files
- `morgul`: correction of experimental data

The former takes the published gain correction tables and three "dark" runs collected with no photon exposure to determine the pedestal values for the three gain modes (g0, g1, g2) at whatever you have for the current integration time and temperature on the chiller, ideally performed within an hour of the data being collected. The other applies these correction files to raw data to give corrected data (with the photon energy), with output compressed with bitshuffle / LZ4 to HDF5.

## To Do

Tasks for `morannon`:
- [ ] determine trusted pixel masks from dark data (e.g. wrong gain mode, surprising values) -> `m0`, `m1`, `m2` data sets in HDF5 output
- [ ] write structured data to pedestal so more than one module can go in file

Tasks for `morgul`:
- [ ] use gain maps already written to HDF5 file
- [ ] expand data from ASICs
- [ ] mask bad pixels as `0xffffffff`

## Usage

Initial set up:

```
python3 ~/git/jungfrau-commissioning/morgul/morannon.py --init jf1md
```

Pedestal calculation:

```
python3 ~/git/jungfrau-commissioning/morgul/morannon.py -0 3_data_0_0_100.h5 jf1md0
python3 ~/git/jungfrau-commissioning/morgul/morannon.py -0 3_data_1_0_100.h5 jf1md1
```

Correction:

```
python3 ~/git/jungfrau-commissioning/morgul/morgul.py -p ../20230612_162257/jf1md0_pedestal.h5 jf1md -m M420 -e 8.04 -d 3_data_0_0_100.h5
python3 ~/git/jungfrau-commissioning/morgul/morgul.py -p ../20230612_162257/jf1md1_pedestal.h5 jf1md -m M418 -e 8.04 -d 3_data_1_0_100.h5
```
