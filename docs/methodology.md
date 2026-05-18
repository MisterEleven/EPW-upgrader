# Methodology

This document describes the scientific and algorithmic approach used by **epwupgrader**
to transform a present-day EnergyPlus Weather (EPW) file into a future-climate EPW file.

---

## Table of Contents

1. [Why Morphing Instead of Raw GCM Replacement](#1-why-morphing-instead-of-raw-gcm-replacement)
2. [Temperature Morphing — Belcher Equations](#2-temperature-morphing--belcher-equations)
3. [Psychrometric Recalculation](#3-psychrometric-recalculation)
4. [Solar Radiation Morphing](#4-solar-radiation-morphing)
5. [Wind Speed Morphing](#5-wind-speed-morphing)
6. [Tail Amplification](#6-tail-amplification)
7. [Temporal Interpolation to Target Year](#7-temporal-interpolation-to-target-year)
8. [GCM Anomaly Data Tables](#8-gcm-anomaly-data-tables)
9. [Limitations and Future Work](#9-limitations-and-future-work)

---

## 1. Why Morphing Instead of Raw GCM Replacement

General Circulation Models (GCMs) operate at spatial resolutions of roughly 50–200 km
per grid cell and at temporal resolutions of monthly means. Building performance
simulation (BPS) tools such as EnergyPlus require sub-hourly or hourly weather sequences
that capture the *diurnal cycle*, *local microclimate*, and *realistic meteorological
variability* of the specific site.

Directly substituting GCM output for observed hourly data introduces two fundamental
problems:

1. **Spatial mismatch** — a GCM cell average smooths out urban heat islands, coastal
   breezes, topographic shading and other features that are critical for building loads.
2. **Temporal structure loss** — monthly or seasonal GCM means do not carry the
   hour-to-hour correlations between temperature, humidity, wind and solar radiation
   that drive peak cooling and heating demand.

The **morphing method** (Belcher, Hacker & Powell, 2005) resolves both problems by
treating GCM output as a *correction signal* applied on top of a high-resolution
observed baseline (the existing EPW file). The baseline preserves local diurnal cycles
and meteorological covariance; the GCM provides the climate-change signal. This approach:

- Retains the statistical character of the observed sequence.
- Requires only monthly GCM anomalies, which are the most reliable quantity that GCMs
  produce.
- Allows independent treatment of variables for which the GCM is most reliable
  (temperature mean shift) versus those where only fractional changes are credible
  (radiation, wind).

---

## 2. Temperature Morphing — Belcher Equations

### Notation

| Symbol  | Meaning |
|---------|---------|
| T(h)    | Dry-bulb temperature of hour *h* in the baseline EPW (°C) |
| T'(h)   | Morphed dry-bulb temperature (°C) |
| ΔT_m    | GCM monthly mean temperature change for month *m* (°C) |
| α_T,m   | GCM monthly fractional change in diurnal temperature range for month *m* |
| T̄_m   | Monthly mean of T(h) in the baseline EPW for month *m* (°C) |

### Belcher Equation 1 — Additive shift (mean warming)

The simplest morphing operator shifts every hour by the GCM monthly mean change:

```
T'(h) = T(h) + ΔT_m(h)
```

This is the primary operator implemented in `morph_temperature`. Each hour is assigned
the ΔT value for its calendar month, so the 12-element `monthly_delta_t` list maps
directly onto the 12 calendar months (index 0 = January, index 11 = December).

### Belcher Equation 3 — Multiplicative stretch (diurnal range change)

The full Belcher Eq. 3 also modulates the diurnal temperature range:

```
T'(h) = T̄_m + ΔT_m + α_T,m · (T(h) − T̄_m)
```

Where:
- `T̄_m` is the mean of all hourly values in month *m* of the baseline file.
- `α_T,m` is the fractional change in the diurnal temperature range predicted by the
  GCM. A value of α > 1 means the diurnal range widens (hotter days, cooler nights
  relative to the new mean); α < 1 means it narrows.

In the current implementation the additive form (Eq. 1) is applied. Eq. 3 represents
a natural extension when GCM output provides reliable diurnal-range anomalies.

### EPW Column

Dry-bulb temperature occupies **column index 6** (0-based) of each EPW data row,
corresponding to EPW field 7 in 1-based numbering.

---

## 3. Psychrometric Recalculation

### Why It Is Mandatory

Dry-bulb temperature and moisture content are not independent in an EPW file. An EPW
row stores three inter-related humidity quantities:

| EPW Col (0-based) | Field name            |
|-------------------|-----------------------|
| 6                 | Dry-bulb temperature  |
| 7                 | Dew-point temperature |
| 8                 | Relative humidity     |

When dry-bulb temperature is morphed upward by ΔT, the **actual water vapour content
of the air** (i.e. the absolute humidity or vapour pressure) does not change — it is
a conserved quantity. However, the *saturation* vapour pressure rises steeply with
temperature (Clausius–Clapeyron relationship). If the EPW relative humidity and
dew-point fields are left unchanged after the dry-bulb shift, the file becomes
thermodynamically inconsistent: the reported RH would imply a higher absolute moisture
content than physically existed in the baseline, and building simulation engines would
compute incorrect latent cooling loads.

`morph_temperature` therefore calls `recalculate_rh_after_temp_shift` and
`recalculate_dew_point_after_temp_shift` for every morphed hour immediately after
applying ΔT.

### The Magnus–Tetens Formula

The saturation vapour pressure E_s (Pa) at temperature T (°C) is:

```
E_s(T) = E_0 · exp( A · T / (B + T) )
```

With the constants used in `psychrometrics.py`:

| Constant | Value  | Unit |
|----------|--------|------|
| E_0      | 611.2  | Pa   |
| A        | 17.625 | —    |
| B        | 243.04 | °C   |

This is the WMO-recommended form of the Magnus–Tetens approximation (Alduchov &
Eskridge, 1996). It is accurate to within ±0.1 % over the range −40 °C to +60 °C,
which covers all conditions encountered in building simulation.

### Step-by-Step Recalculation

**Given:** original dry-bulb T_orig (°C), temperature shift ΔT (°C), original
relative humidity RH_orig (%), original dew-point T_dew_orig (°C).

**Step 1 — Actual vapour pressure from dew-point**

The dew-point is defined as the temperature at which the air is saturated at its
current absolute moisture level, so:

```
E_actual = E_0 · exp( A · T_dew_orig / (B + T_dew_orig) )
```

**Step 2 — Saturation vapour pressure at new dry-bulb**

```
T_new    = T_orig + ΔT
E_s_new  = E_0 · exp( A · T_new / (B + T_new) )
```

**Step 3 — New relative humidity**

Relative humidity is the ratio of actual to saturation vapour pressure:

```
RH_new = 100 · E_actual / E_s_new
```

Clamped to the range [0, 100] % to handle any floating-point edge cases.

**Step 4 — New dew-point**

Invert the Magnus–Tetens formula, solving for T given E = E_actual:

```
ln_ratio   = ln(E_actual / E_0)
T_dew_new  = B · ln_ratio / (A − ln_ratio)
```

This is the exact algebraic inverse of the Magnus–Tetens equation.

### Worked Example

Suppose an EPW hour has:

- T_orig = 25.0 °C
- T_dew_orig = 15.0 °C
- RH_orig ≈ 53.5 %
- Applied ΔT = +3.5 °C (typical SSP5-8.5 summer value)

**Step 1 — Actual vapour pressure**

```
E_actual = 611.2 · exp(17.625 · 15.0 / (243.04 + 15.0))
         = 611.2 · exp(264.375 / 258.04)
         = 611.2 · exp(1.02454)
         = 611.2 · 2.7855
         ≈ 1702.8 Pa
```

**Step 2 — Saturation vapour pressure at T_new = 28.5 °C**

```
E_s_new = 611.2 · exp(17.625 · 28.5 / (243.04 + 28.5))
        = 611.2 · exp(502.3125 / 271.54)
        = 611.2 · exp(1.84981)
        = 611.2 · 6.3601
        ≈ 3886.3 Pa
```

**Step 3 — New relative humidity**

```
RH_new = 100 · 1702.8 / 3886.3
       ≈ 43.8 %
```

The relative humidity drops from ~53.5 % to ~43.8 %, consistent with the physical
intuition that the same parcel of air feels drier as it warms.

**Step 4 — New dew-point**

```
ln_ratio  = ln(1702.8 / 611.2) = ln(2.7855) ≈ 1.02454
T_dew_new = 243.04 · 1.02454 / (17.625 − 1.02454)
          = 248.997 / 16.6005
          ≈ 15.0 °C
```

The dew-point is unchanged (as expected — absolute moisture is conserved), confirming
that the inversion formula is self-consistent.

---

## 4. Solar Radiation Morphing

### Columns Morphed

| EPW Col (0-based) | Field name                          | Morphing factor  |
|-------------------|-------------------------------------|------------------|
| 13                | Global Horizontal Irradiance (GHI)  | alpha_ghi        |
| 14                | Direct Normal Irradiance (DNI)      | alpha_dni        |
| 15                | Diffuse Horizontal Irradiance (DHI) | alpha_dhi        |

### Morphing Operator

Each radiation variable R is morphed multiplicatively:

```
R'(h) = R(h) · (1 + α_R,m(h))
```

Where α_R,m is the fractional change for the relevant variable and month. A value of
α = +0.05 represents a 5 % increase; α = −0.03 represents a 3 % decrease.

### Why Multiplicative (Not Additive)

Solar irradiance is inherently non-negative and its diurnal profile is dominated by
solar geometry rather than meteorological variability. Multiplicative morphing preserves:

1. Zero values during night hours (multiplying zero by any factor gives zero).
2. The relative shape of the diurnal curve (peaks scale proportionally).
3. Physical non-negativity at every hour.

An additive operator could produce negative irradiance values at twilight hours where
baseline values are small but non-zero — a physically invalid result.

### Non-Negativity Clipping

Despite the multiplicative form, a fractional factor close to −1 could theoretically
produce a negative result. `morph_radiation` therefore clips all morphed radiation
values to a minimum of **0 W/m²**:

```python
morphed_value = max(0, original_value * (1 + alpha_m))
```

### GHI, DNI and DHI Are Morphed Independently

GCM projections can show differing trends for beam versus diffuse components — for
example, increased aerosol loading can reduce DNI while leaving GHI relatively
unchanged. Providing three independent monthly anomaly lists (`monthly_alpha_ghi`,
`monthly_alpha_dni`, `monthly_alpha_dhi`) allows these divergent trends to be captured
without forcing a fixed relationship between the components.

---

## 5. Wind Speed Morphing

### EPW Column

Wind speed occupies **column index 21** (0-based) of each EPW data row.

### Morphing Operator

Wind speed is morphed multiplicatively by a monthly fractional change factor:

```
W'(h) = W(h) · (1 + α_W,m(h))
```

Where α_W,m is the wind-speed fractional change for month *m*.

### Rationale for Multiplicative Form

Like solar radiation, wind speed is non-negative and its magnitude varies over several
orders of magnitude between calm and stormy conditions. A multiplicative operator
preserves calm hours (zero wind stays zero), maintains the relative intensity of wind
events, and prevents physically impossible negative wind speeds. GCMs provide more
credible fractional changes in wind speed than absolute changes, further justifying
this form.

---

## 6. Tail Amplification

### Scientific Motivation

GCM projections and observational studies both indicate that under high-emission
scenarios, extreme heat events warm *faster* than the mean. The tail of the temperature
distribution shifts disproportionately because:

- Soil moisture feedbacks amplify hot-day temperatures in continental interiors.
- Changes in atmospheric circulation increase the frequency and persistence of blocking
  patterns that produce heat waves.
- The urban heat island effect interacts nonlinearly with background warming.

A simple additive mean-shift (Belcher Eq. 1) applied uniformly to all hours
underestimates the warming of the most extreme hours and therefore underestimates peak
cooling loads under SSP5-8.5.

### Implementation

After the base ΔT shift is applied to an hour, `morph_temperature` checks whether the
**original** (pre-morph) dry-bulb temperature exceeds the **99th percentile** of all
dry-bulb temperatures in the same calendar month across the baseline EPW. If it does,
and the active scenario is `"SSP5-8.5"`, an additional amplification is applied:

```
T'(h) = T(h) + ΔT_m · 1.5    [if T(h) > P99_m  AND  scenario == "SSP5-8.5"]
T'(h) = T(h) + ΔT_m           [otherwise]
```

The factor **1.5** means that the hottest 1 % of hours in a given month warm at
50 % more than the monthly mean rate. This is consistent with the spread of projected
extreme-heat anomalies in CMIP6 ensembles under SSP5-8.5.

Tail amplification is **not** applied under `"SSP2-4.5"`, reflecting the lower
radiative forcing and reduced extreme-heat amplification under that scenario.

Psychrometric quantities (dew-point, relative humidity) are recalculated using the
tail-amplified temperature, not the base-shifted temperature, so the final EPW row is
always internally consistent.

---

## 7. Temporal Interpolation to Target<function_calls>
<invoke name="read_text_file">
<parameter name="path">/app/projects/epwupgrader/epwupgrader/anomalies.py