# Methodology

epwupgrader uses *morphing* (Belcher, Hacker & Powell 2005). Global climate models are too coarse
for hourly building simulation. So the measured hourly series is kept, and only the model's
monthly changes are applied on top. This preserves the local daily cycle and the links between
variables.

## Equations

For hour *h* in month *m*:

| Operation | Formula | Used for |
|---|---|---|
| shift | `x' = x + Δx_m` | dry bulb (default) |
| shift + stretch | `x' = x + Δx_m + α_m (x − x̄_m)` | dry bulb (API, `alpha_t`) |
| stretch | `x' = α_m · x`, clipped ≥ 0 | GHI, DNI, DHI, wind speed |

`x̄_m` is the monthly mean of the input file. Coefficients can be scalars, 12 monthly values or
one value per hour.

## Humidity

Vapour pressure is held constant. The dew point stays the same, capped at the new dry bulb. RH is
scaled:

```
RH' = RH · e_s(T) / e_s(T')
e_s(T) = 611.2 · exp(17.625 T / (243.04 + T))   [Pa]   (Alduchov & Eskridge 1996)
```

This equals `100 · e_s(T_dew) / e_s(T')` when the source RH and dew point agree. TMYx files often
disagree by a few percent, and scaling keeps RH from ever rising under warming.

Warmer air with the same moisture means lower RH. In reality absolute humidity rises with warming
(about 7 %/K), so this is a conservative simplification.

## Time interpolation

The built-in tables give changes at 2100 relative to the IPCC AR6 reference period 1995–2014
(midpoint 2005). Change is assumed linear in time, so a file is morphed by the change between
its baseline year *b* and the target year *t*:

```
ΔT = ΔT_2100 · (t − b) / (2100 − 2005)
α  = 1 + (α_2100 − 1) · (t − b) / (2100 − 2005)
```

The baseline is the midpoint of the file's `Period of Record` (e.g. TMYx 2011–2025 gives 2018),
else the median data year, or `--baseline-year`.

## Caveats

- The built-in tables are generic placeholders, not downscaled for any site. Use `--anomalies`
  with regional data for real studies.
- SSP5-8.5 warming accelerates, so pinning a straight line at 2100 overestimates the change for
  intermediate years.
- Not morphed: longwave sky radiation, illuminance, precipitation, pressure (pressure is available
  through the API). The `DESIGN CONDITIONS` and `GROUND TEMPERATURES` headers still describe the
  baseline climate.

## Reference

Belcher, S. E., Hacker, J. N., & Powell, D. S. (2005). Constructing design weather data for future
climates. *Building Services Engineering Research and Technology*, 26(1), 49–61.
