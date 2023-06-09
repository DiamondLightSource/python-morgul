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
