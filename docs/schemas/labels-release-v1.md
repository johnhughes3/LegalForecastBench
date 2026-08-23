# `legalforecast.labels-release.v1`

`labels-release.v1` is the separate outcome-bearing scoring manifest. It uses the same canonical artifact JSON profile and computes `release_digest` over the object with that field omitted.

The release binds one forecast release digest, one scoring policy, and one sorted, unique binary outcome for every forecast prediction unit. Release IDs, unit counts, unit sets, and the forecast digest must match the paired forecast release exactly. Forecast execution APIs accept neither this manifest nor a path to it.
