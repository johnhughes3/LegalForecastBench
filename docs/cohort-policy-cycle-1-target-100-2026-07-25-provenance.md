# Cycle 1 exact-100 cohort-policy provenance

This note records why every value in `cohort-policy-cycle-1-target-100-2026-07-25-decisions.json` is authorized or mechanically derived.
It is not a policy artifact and is never consumed as runtime authority.

## Human authority

- `LegalForecastBench-5qd6.86` records John's exact first-run `launch_case_count=100`, with acquisition toward at least 150 retained only as a nonblocking reserve; it closed on 2026-07-17 before packet exposure.
- On 2026-07-25 John explicitly changed the pending first-run launch target from 150 to 100 and directed that everything else remain unchanged. `LegalForecastBench-5qd6.75.16.4` records that amendment in its durable notes; acquisition toward 150 remains the pre-existing nonblocking reserve.
- The immediately preceding exact-148 policy draft recorded the unchanged acquisition values in `LegalForecastBench-5qd6.75.8` on 2026-07-25: current cycle hash, `2026-06-30` anchor, source window through `2026-07-23`, cheapest-complete selection, `$567.30` cycle cap, `$73.20` per-case cap, 14-day overlap, packet completeness, quarantine and same-cap replacement. The exact-100 decisions change only the launch target and terminal claim tier, as John directed.
- The 400-prediction-unit claim floor is preserved from the prior generated exact-100 policy with identity `d27bf66cd895ec42b912aafc535bf53cf9e9d38182bff9e32ff5ac72c0bc0128`. It can only downgrade the public claim class to provisional feasibility; it cannot admit a case, relax a quality gate, authorize spending, or change the frozen exact-100 denominator.

## Mechanically derived evidence

- `cycle_acquisition_hash`: `35f70123bfc966512d61119746ba09716332a181c074f131d553b56b610641cb`, from the complete and saturated `cycle1-final153-current-policy-union-main-911371f-v1` manifest.
- `eligibility_anchor`: `2026-06-30`, unchanged from the user-specified eligibility anchor.
- `search_window_end`: `2026-07-23`, the terminal date bound of the authenticated source snapshot used by the exact-100 preparation.
- `cycle_id`: `cycle-1-target-100-2026-07-25`, a unique descriptive identifier with no policy effect.
- Current reason-code lists are supplied by `generate-cohort-policy` from the cycle-store taxonomy rather than copied from a stale artifact.

The decisions input has SHA-256 `c5e39a3a31f49327ec3cc83222ed6dd2e5960070cc16dd48ab930dbef508ec29`.
The generated policy has internal identity `0f115ac1a2fe1eb2ef3f4c92113fdfa2d5773ba534e9951b9ba8e67134faebed` and complete-file SHA-256 `1b2934646dffa68660a84fd2309b62852bdf6d36c26fdbc083ae792de3ea0a8b`.
The main disclosure registry intentionally leaves that identity unprovisioned until John supplies the hardware-backed reviewer policy tracked by `LegalForecastBench-5qd6.39.7.1`.
