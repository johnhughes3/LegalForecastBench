/** Pinned upstream Harvey LAB revision the audit and the explorer are built on. */
export const HARVEY_COMMIT = "1dd81403b2fbb60596f7aea3fcecafad7bf73143";

const RAW = `https://raw.githubusercontent.com/harveyai/harvey-labs/${HARVEY_COMMIT}/tasks/litigation-dispute-resolution`;
const BLOB = `https://github.com/harveyai/harvey-labs/blob/${HARVEY_COMMIT}/tasks/litigation-dispute-resolution`;
const TREE = `https://github.com/harveyai/harvey-labs/tree/${HARVEY_COMMIT}/tasks/litigation-dispute-resolution`;

export const rawTaskUrl = (task: string): string => `${RAW}/${task}/task.json`;

export const upstreamTaskUrl = (task: string, line?: number): string =>
	`${BLOB}/${task}/task.json${line === undefined ? "" : `#L${line}`}`;

export const upstreamDocumentsUrl = (task: string): string =>
	`${TREE}/${task}/documents`;

export const upstreamDocumentUrl = (task: string, file: string): string =>
	`${BLOB}/${task}/documents/${encodeURIComponent(file)}`;
