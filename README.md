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
