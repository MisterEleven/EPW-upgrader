"""
Live smoke-test suite for epwupgrader.
Run with: python run_tests.py
"""
import sys
import traceback

sys.path.insert(0, '/app/projects/epwupgrader')

# Clear any stale cached modules from previous broken versions
for mod in list(sys.modules.keys()):
    if 'epwupgrader' in mod:
        del sys.modules[mod]

results = {}

# -----------------------------------------------------------------------
# TEST 1: Package imports cleanly
# -----------------------------------------------------------------------
try:
    import epwupgrader
    names = dir(epwupgrader)
    assert 'parse_epw' in names
    assert 'write_epw' in names
    assert 'get_monthly_anomalies' in names
    assert 'morph_temperature' in names
    assert 'saturation_vapor_pressure' in names
    print("TEST1 PASS - import epwupgrader OK, exports:", [n for n in names if not n.startswith('_')])
    results['TEST1'] = ('PASS', 'OK')
except Exception:
    tb = traceback.format_exc()
    print("TEST1 FAIL:", tb)
    results['TEST1'] = ('FAIL', tb)

# -----------------------------------------------------------------------
# TEST 2: get_monthly_anomalies returns correct structure
# -----------------------------------------------------------------------
try:
    from epwupgrader.gcm_data import get_monthly_anomalies
    anomalies = get_monthly_anomalies(scenario='SSP5-8.5', target_year=2050)
    assert isinstance(anomalies, dict), f"Must be dict, got {type(anomalies)}"
    assert len(anomalies) == 12, f"Must have 12 months, got {len(anomalies)}"
    for m in range(1, 13):
        assert m in anomalies, f"Month {m} missing"
        row = anomalies[m]
        for key in ('delta_temp_c', 'alpha_solar', 'beta_wind', 'tail_amplification_factor'):
            assert key in row, f"Key '{key}' missing in month {m}: {row}"
        assert isinstance(row['delta_temp_c'], float), f"delta_temp_c not float: {row['delta_temp_c']}"
    print(f"TEST2 PASS - anomalies OK. Month 1: {anomalies[1]}")
    results['TEST2'] = ('PASS', str(anomalies[1]))
except Exception:
    tb = traceback.format_exc()
    print("TEST2 FAIL:", tb)
    results['TEST2'] = ('FAIL', tb)

# -----------------------------------------------------------------------
# TEST 3: parse_epw returns correct 3-tuple
# -----------------------------------------------------------------------
try:
    # Build a minimal valid EPW with exactly 8760 data rows
    header = [
        "LOCATION,TestCity,TestState,TestCountry,TMY3,999999,51.5,-0.1,0.0,10.0",
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,Test EPW file for smoke testing",
        "COMMENTS 2,Minimal synthetic data",
        "DATA PERIODS,1,1,Data,Sunday, 1/ 1,12/31",
    ]
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    data_rows = []
    for month_idx, days in enumerate(days_in_month, start=1):
        for day in range(1, days + 1):
            for hour in range(1, 25):
                fields = [
                    1999, month_idx, day, hour, 0,
                    "?9?9?9",
                    15.0, 10.0, 65, 101325,
                    0, 1355, 310, 500, 800, 100,
                    0, 0, 0, 0,
                    180, 3.0,
                    3, 3, 10.0, 77777, 9, 999999999,
                    80, 0.09, 0, 88, 0.200, 0.0, 1.0
                ]
                data_rows.append(','.join(str(f) for f in fields))

    epw_content = '\n'.join(header + data_rows) + '\n'
    with open('/tmp/smoke_test.epw', 'w') as f:
        f.write(epw_content)

    from epwupgrader.parser import parse_epw
    result = parse_epw('/tmp/smoke_test.epw')

    assert len(result) == 3, f"Expected 3-tuple, got {len(result)}-tuple"
    df, metadata, header_lines = result

    assert hasattr(df, 'shape'), f"First element must be DataFrame, got {type(df)}"
    assert len(df) == 8760, f"Expected 8760 rows, got {len(df)}"
    assert df.shape[1] == 35, f"Expected 35 columns, got {df.shape[1]}"
    assert isinstance(metadata, dict), f"metadata must be dict, got {type(metadata)}"
    assert 'city' in metadata, f"'city' missing from metadata"
    assert 'latitude' in metadata, f"'latitude' missing from metadata"
    assert metadata['city'] == 'TestCity', f"city mismatch: {metadata['city']}"
    assert isinstance(header_lines, list), f"header_lines must be list, got {type(header_lines)}"
    assert len(header_lines) == 8, f"Expected 8 header lines, got {len(header_lines)}"

    print(f"TEST3 PASS - parse_epw: shape={df.shape}, city={metadata['city']}, lat={metadata['latitude']}, headers={len(header_lines)}")
    results['TEST3'] = ('PASS', f"shape={df.shape}")
except Exception:
    tb = traceback.format_exc()
    print("TEST3 FAIL:", tb)
    results['TEST3'] = ('FAIL', tb)

# -----------------------------------------------------------------------
# TEST 4: write_epw signature is (df, header_lines, output_path)
# -----------------------------------------------------------------------
try:
    import inspect
    from epwupgrader.writer import write_epw
    sig = inspect.signature(write_epw)
    params = list(sig.parameters.keys())
    assert params[0] == 'df', f"Expected 'df' at pos 0, got '{params[0]}'"
    assert params[1] == 'header_lines', f"Expected 'header_lines' at pos 1, got '{params[1]}'"
    assert params[2] == 'output_path', f"Expected 'output_path' at pos 2, got '{params[2]}'"
    print(f"TEST4 PASS - write_epw signature correct: {params}")
    results['TEST4'] = ('PASS', str(params))
except Exception:
    tb = traceback.format_exc()
    print("TEST4 FAIL:", tb)
    results['TEST4'] = ('FAIL', tb)

# -----------------------------------------------------------------------
# TEST 5: End-to-end pipeline (parse -> morph -> write -> re-parse)
# -----------------------------------------------------------------------
try:
    import numpy as np
    from epwupgrader.parser import parse_epw
    from epwupgrader.gcm_data import get_monthly_anomalies
    from epwupgrader.morphing import morph_temperature, morph_radiation, morph_wind_speed
    from epwupgrader.writer import write_epw

    df, metadata, header_lines = parse_epw('/tmp/smoke_test.epw')
    anomalies = get_monthly_anomalies(scenario='SSP5-8.5', target_year=2050)

    n = len(df)
    delta_temp  = np.zeros(n, dtype=float)
    alpha_solar = np.ones(n,  dtype=float)
    alpha_wind  = np.ones(n,  dtype=float)

    months = df['month'].to_numpy(dtype=int)
    for m in range(1, 13):
        mask = months == m
        delta_temp[mask]  = anomalies[m]['delta_temp_c']
        alpha_solar[mask] = anomalies[m]['alpha_solar']
        alpha_wind[mask]  = anomalies[m]['beta_wind']

    morphed = morph_temperature(df, delta_t=delta_temp)
    morphed = morph_radiation(morphed, alpha_ghi=alpha_solar,
                              alpha_dni=alpha_solar, alpha_dhi=alpha_solar)
    morphed = morph_wind_speed(morphed, alpha_ws=alpha_wind)

    assert len(morphed) == 8760, f"Morphed df has {len(morphed)} rows"

    orig_mean_t  = df['dry_bulb_temperature'].mean()
    morph_mean_t = morphed['dry_bulb_temperature'].mean()
    assert morph_mean_t > orig_mean_t, f"Morphed T should be higher: {morph_mean_t:.2f} vs {orig_mean_t:.2f}"

    orig_mean_rh  = df['relative_humidity'].mean()
    morph_mean_rh = morphed['relative_humidity'].mean()
    assert morph_mean_rh < orig_mean_rh, f"Morphed RH should be lower: {morph_mean_rh:.2f} vs {orig_mean_rh:.2f}"

    for col in ['global_horiz_radiation', 'direct_normal_radiation', 'diffuse_horiz_radiation']:
        assert (morphed[col] >= 0).all(), f"Negative values in {col}"

    write_epw(morphed, header_lines, '/tmp/smoke_output_2050.epw')

    df2, meta2, hdr2 = parse_epw('/tmp/smoke_output_2050.epw')
    assert len(df2) == 8760, f"Re-parsed EPW has {len(df2)} rows"
    assert df2.shape[1] == 35

    print(f"TEST5 PASS - end-to-end pipeline OK")
    print(f"  T: {orig_mean_t:.2f} -> {morph_mean_t:.2f} degC (+{morph_mean_t - orig_mean_t:.2f})")
    print(f"  RH: {orig_mean_rh:.1f}% -> {morph_mean_rh:.1f}%")
    results['TEST5'] = ('PASS', f"T+{morph_mean_t - orig_mean_t:.2f}C, RH {orig_mean_rh:.1f}->{morph_mean_rh:.1f}%")
except Exception:
    tb = traceback.format_exc()
    print("TEST5 FAIL:", tb)
    results['TEST5'] = ('FAIL', tb)

# -----------------------------------------------------------------------
# TEST 6: CLI parser works without crashing
# -----------------------------------------------------------------------
try:
    from epwupgrader.cli import _build_parser
    p = _build_parser()
    args = p.parse_args(['--input', 'x.epw', '--output', 'y.epw', '--year', '2050'])
    assert args.year == 2050
    assert args.input == 'x.epw'
    assert args.output == 'y.epw'
    assert args.scenario == 'SSP5-8.5'
    assert args.verbose == False
    print(f"TEST6 PASS - CLI parser OK: {vars(args)}")
    results['TEST6'] = ('PASS', str(vars(args)))
except Exception:
    tb = traceback.format_exc()
    print("TEST6 FAIL:", tb)
    results['TEST6'] = ('FAIL', tb)

# -----------------------------------------------------------------------
# SUMMARY
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)
all_pass = True
for k, (status, detail) in sorted(results.items()):
    icon = "OK" if status == 'PASS' else "FAIL"
    print(f"  {k}: {icon}  {str(detail)[:100]}")
    if status != 'PASS':
        all_pass = False

print("=" * 60)
if all_pass:
    print("ALL TESTS PASSED")
    sys.exit(0)
else:
    print("ONE OR MORE TESTS FAILED")
    sys.exit(1)