# `legalforecast.labels-release.v1`

`labels-release.v1` is the separate outcome-bearing scoring manifest. It uses the same canonical artifact JSON profile and computes `release_digest` over the object with that field omitted.

The release binds one forecast release digest, one scoring policy, and one sorted, unique binary outcome for every scoreable forecast prediction unit. Unscoreable units remain available to the model through the forecast release but have no fabricated outcome. Release IDs, scoreable unit sets, and the forecast digest must match the paired forecast release exactly; the labels `unit_count` matches the number of outcomes. Forecast execution APIs accept neither this manifest nor a path to it.
