// Archived copies of the third-party benchmarks the audits cite, at the cited commits.
// tests/test_benchmark_snapshots.py checks these commits against the audit code's pins.
import manifest from "./benchmark-snapshots.json";

export interface BenchmarkSnapshot {
	benchmark: string;
	audit: string;
	upstream: string;
	commit: string;
	committed: string;
	license: string;
	license_url: string;
	rights: string;
	citation?: string;
	archive: string;
	bytes: number;
	sha256: string;
	files: number;
}

export const benchmarkSnapshots: {
	doi: string;
	record_url: string;
	verifier: { file: string; sha256: string };
	snapshots: BenchmarkSnapshot[];
} = manifest;

export const snapshotFileUrl = (name: string): string =>
	`${benchmarkSnapshots.record_url}/files/${encodeURIComponent(name)}?download=1`;

export const formatBytes = (bytes: number): string =>
	bytes >= 1e9
		? `${(bytes / 1e9).toFixed(2)} GB`
		: `${Math.round(bytes / 1e6)} MB`;
