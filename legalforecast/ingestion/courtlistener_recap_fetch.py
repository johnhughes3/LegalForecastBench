"""Guarded individual-document purchases through CourtListener RECAP Fetch."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from http.client import HTTPMessage
from typing import IO, Any, Protocol, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerCapability,
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseResult,
    CaseDevPacerPurchaseStatus,
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerError,
)
from legalforecast.ingestion.missing_core_budget import MissingCoreBudgetPlan
from legalforecast.ingestion.recap_fetch_attempt_policy import UNKNOWN_STATUS_EVIDENCE
from legalforecast.ingestion.recap_fetch_broker import (
    BrokerDefiniteRejection,
    BrokerOutcomeUnknown,
    broker_reconciliation_record,
    validate_broker_receipt,
)
from legalforecast.ingestion.recap_fetch_broker_policy import (
    COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE,
)

COURTLISTENER_RECAP_FETCH_PROVIDER = "courtlistener.recap-fetch+pacer"
_DEFAULT_BASE_URL = "https://www.courtlistener.com/api/rest/v4"
_ALLOWED_HOSTS = frozenset({"www.courtlistener.com"})
_RETRYABLE = frozenset({429, 500, 502, 503, 504})
_TERMINAL_FAILURES = frozenset({3, 6, 7})


class CourtListenerRecapFetchError(RuntimeError):
    """Raised when RECAP Fetch cannot proceed without weakening a safety gate."""


class CourtListenerRecapFetchOutcomeUnknown(CourtListenerRecapFetchError):
    """Raised when the paid POST may have reached CourtListener."""


@dataclass(frozen=True, slots=True)
class CourtListenerRecapFetchConfig:
    api_token: str = field(repr=False)
    base_url: str = _DEFAULT_BASE_URL
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> CourtListenerRecapFetchConfig:
        values = os.environ if environ is None else environ
        missing = tuple(
            name
            for name in ("COURTLISTENER_API_TOKEN",)
            if not values.get(name, "").strip()
        )
        if missing:
            raise CourtListenerRecapFetchError(
                "missing required purchase credentials: " + ", ".join(missing)
            )
        return cls(
            api_token=values["COURTLISTENER_API_TOKEN"].strip(),
            base_url=values.get("COURTLISTENER_BASE_URL", _DEFAULT_BASE_URL),
            timeout_seconds=float(values.get("COURTLISTENER_TIMEOUT_SECONDS", "30")),
        )


@dataclass(frozen=True, slots=True)
class RecapFetchHTTPResponse:
    status_code: int
    payload: Mapping[str, Any]
    headers: Mapping[str, str] = field(default_factory=lambda: {})


class RecapFetchTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        path: str,
        form: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> RecapFetchHTTPResponse: ...


class RecapFetchPurchaseBroker(Protocol):
    """Budget-enforcing custody boundary for the PACER credentialed POST."""

    @property
    def paid_dispatch_count(self) -> int:
        """Return charge-bearing submissions that reached the transport boundary."""

        raise NotImplementedError

    def submit(self, request: Mapping[str, str]) -> Mapping[str, Any]: ...

    def receipt(self, operation_key: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class RecordedRecapFetchResponse:
    method: str
    path: str
    form: Mapping[str, str]
    status_code: int
    payload: Mapping[str, Any]


class FixtureRecapFetchTransport:
    """Strict offline transport that proves the exact request sequence."""

    def __init__(self, responses: Sequence[RecordedRecapFetchResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, str]]] = []

    @classmethod
    def from_jsonl(cls, path: str | os.PathLike[str]) -> FixtureRecapFetchTransport:
        responses: list[RecordedRecapFetchResponse] = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw: object = json.loads(line)
                if not isinstance(raw, Mapping):
                    raise CourtListenerRecapFetchError("fixture row must be an object")
                record = cast(Mapping[str, object], raw)
                payload = record.get("payload")
                form = record.get("form", {})
                if not isinstance(payload, Mapping) or not isinstance(form, Mapping):
                    raise CourtListenerRecapFetchError(
                        "fixture payload and form must be objects"
                    )
                responses.append(
                    RecordedRecapFetchResponse(
                        method=str(record["method"]).upper(),
                        path=str(record["path"]),
                        form={
                            str(key): str(value)
                            for key, value in cast(
                                Mapping[object, object], form
                            ).items()
                        },
                        status_code=int(cast(str | int, record["status_code"])),
                        payload=cast(Mapping[str, Any], payload),
                    )
                )
        return cls(responses)

    def request(
        self,
        *,
        method: str,
        path: str,
        form: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> RecapFetchHTTPResponse:
        del headers, timeout_seconds
        normalized = method.upper()
        actual_form = dict(form)
        self.requests.append((normalized, path, actual_form))
        if not self._responses:
            raise CourtListenerRecapFetchError("no fixture response remains")
        expected = self._responses.pop(0)
        if (expected.method, expected.path, dict(expected.form)) != (
            normalized,
            path,
            actual_form,
        ):
            raise CourtListenerRecapFetchError("fixture request mismatch")
        return RecapFetchHTTPResponse(expected.status_code, expected.payload)


class FixtureRecapFetchPurchaseBroker:
    """Offline broker double; no production PACER credential path exists here."""

    def __init__(self, responses: Sequence[Mapping[str, Any]]) -> None:
        self._responses = list(responses)
        self.requests: list[dict[str, str]] = []

    @property
    def paid_dispatch_count(self) -> int:
        """Offline fixtures never cross a charge-bearing transport boundary."""

        return 0

    def submit(self, request: Mapping[str, str]) -> Mapping[str, Any]:
        self.requests.append(dict(request))
        if not self._responses:
            raise CourtListenerRecapFetchOutcomeUnknown(
                "purchase broker outcome is unknown"
            )
        return self._responses.pop(0)

    def receipt(self, operation_key: str) -> Mapping[str, Any]:
        del operation_key
        raise CourtListenerRecapFetchOutcomeUnknown(
            "offline fixture has no broker receipt response"
        )


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        del req, fp, code, msg, headers, newurl
        return None


class UrlLibRecapFetchTransport:
    """HTTPS-only transport that never forwards PACER credentials on redirects."""

    def __init__(self, base_url: str) -> None:
        parsed = urllib.parse.urlparse(base_url)
        host = parsed.hostname.lower() if parsed.hostname else None
        if parsed.scheme != "https" or host not in _ALLOWED_HOSTS:
            raise CourtListenerRecapFetchError(
                "CourtListener base URL must be HTTPS on www.courtlistener.com"
            )
        if parsed.username or parsed.password or parsed.port not in {None, 443}:
            raise CourtListenerRecapFetchError("invalid CourtListener base URL")
        self._base_url = base_url.rstrip("/")
        self._opener = urllib.request.build_opener(_RejectRedirects())

    def request(
        self,
        *,
        method: str,
        path: str,
        form: Mapping[str, str],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> RecapFetchHTTPResponse:
        data = urllib.parse.urlencode(form).encode() if form else None
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            method=method.upper(),
            headers=dict(headers),
        )
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                return RecapFetchHTTPResponse(
                    response.status,
                    _json_object(response.read()),
                    dict(response.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            return RecapFetchHTTPResponse(
                exc.code,
                _json_object(exc.read()),
                dict(exc.headers.items()) if exc.headers else {},
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CourtListenerRecapFetchOutcomeUnknown(
                "CourtListener request outcome is unknown"
            ) from exc


class CourtListenerRecapFetchClient:
    """Execute verified public-document queue requests through one journal."""

    def __init__(
        self,
        config: CourtListenerRecapFetchConfig,
        *,
        journal: CaseDevPurchaseJournal,
        transport: RecapFetchTransport | None = None,
        purchase_broker: RecapFetchPurchaseBroker | None = None,
        before_request: Callable[[str, str], None] | None = None,
        poll_attempts: int = 3,
        poll_backoff_seconds: float = 0.0,
    ) -> None:
        self.config = config
        self.journal = journal
        self.transport = transport or UrlLibRecapFetchTransport(config.base_url)
        self.purchase_broker = purchase_broker
        self.before_request = before_request
        self.poll_attempts = poll_attempts
        self.poll_backoff_seconds = poll_backoff_seconds
        self.courtlistener_request_count = 0

    @property
    def paid_request_count(self) -> int:
        """Return only broker-confirmed charge-bearing transport dispatches."""

        if self.purchase_broker is None:
            return 0
        return self.purchase_broker.paid_dispatch_count

    def execute_purchase_plan(
        self,
        plan: MissingCoreBudgetPlan,
        *,
        public_documents: Mapping[str, Mapping[str, Any]],
        attempt_documents: Mapping[str, Mapping[str, str]] | None = None,
        attempt_policy_sha256: str | None = None,
        live: bool,
        acknowledge_pacer_fees: bool,
    ) -> CaseDevPacerPurchaseResult:
        if plan.dry_run or not live or not acknowledge_pacer_fees:
            raise CourtListenerRecapFetchError(
                "RECAP Fetch requires an executable plan, live flag, and fee "
                "acknowledgment"
            )
        attempt_documents = {} if attempt_documents is None else attempt_documents
        intended = tuple(
            (case_plan.candidate_id, document_id)
            for case_plan in plan.case_plans
            for document_id in case_plan.purchase_document_ids
        )
        intended_candidates = {
            document_id: candidate_id for candidate_id, document_id in intended
        }
        if attempt_documents and attempt_policy_sha256 is None:
            raise CourtListenerRecapFetchError(
                "unknown attempt documents require a verified policy digest"
            )
        if not attempt_documents and attempt_policy_sha256 is not None:
            raise CourtListenerRecapFetchError(
                "attempt policy digest has no authorized documents"
            )
        extra_attempts = set(attempt_documents) - set(intended_candidates)
        if extra_attempts:
            raise CourtListenerRecapFetchError(
                "attempt policy contains unplanned documents: "
                + ", ".join(sorted(extra_attempts))
            )
        for _, document_id in intended:
            metadata = public_documents.get(document_id)
            if metadata is None:
                raise CourtListenerRecapFetchError(
                    f"missing public restriction evidence for {document_id}"
                )
            attempt = attempt_documents.get(document_id)
            if attempt is None:
                _require_explicitly_public(metadata, document_id)
            elif attempt.get("case_id") != intended_candidates[document_id]:
                raise CourtListenerRecapFetchError(
                    f"unknown attempt candidate conflicts for {document_id}"
                )
            else:
                _require_unknown_attempt_evidence(metadata, document_id)
        self.journal.plan(plan)
        if attempt_documents:
            assert attempt_policy_sha256 is not None
            self.journal.authorize_unknown_material_attempts(
                attempt_documents,
                attempt_policy_sha256=attempt_policy_sha256,
            )
        self._recover_receipts(intended)
        self.journal.require_reconciled()
        attempts: list[CaseDevPacerPurchaseAttempt] = []
        for index, (candidate_id, document_id) in enumerate(intended):
            attempt = self._execute_one(candidate_id, document_id)
            attempts.append(attempt)
            if attempt.status is CaseDevPacerPurchaseStatus.UNKNOWN:
                attempts.extend(
                    _attempt(
                        remaining_candidate_id,
                        remaining_document_id,
                        CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
                        "unknown_outcome_before_attempt",
                    )
                    for remaining_candidate_id, remaining_document_id in intended[
                        index + 1 :
                    ]
                )
                break
        return CaseDevPacerPurchaseResult(
            live=True,
            acknowledge_pacer_fees=True,
            capability=CaseDevPacerCapability.DOCUMENT_LEVEL_PURCHASE,
            dry_run=False,
            projected_cost_usd=plan.total_estimated_cost_usd,
            max_projected_budget_usd=plan.max_projected_budget_usd,
            attempts=tuple(attempts),
        )

    def _execute_one(
        self, candidate_id: str, document_id: str
    ) -> CaseDevPacerPurchaseAttempt:
        evidence = self.journal.operation_evidence(document_id)
        status = None if evidence is None else str(evidence["status"])
        if status == "confirmed":
            assert evidence is not None
            if evidence.get("material_authority") == "unknown_status_attempt":
                return _attempt(
                    candidate_id,
                    document_id,
                    CaseDevPacerPurchaseStatus.QUARANTINED,
                    "unknown_status_material_pending_clearance",
                )
            response = _mapping(evidence.get("response"), "confirmed response")
            return _purchased_attempt(candidate_id, document_id, response)
        if status == "failed":
            assert evidence is not None
            return _attempt(
                candidate_id,
                document_id,
                CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                str(evidence.get("error") or "provider confirmed failure"),
            )
        if status == "queued":
            assert evidence is not None
            queued = _mapping(evidence.get("response"), "queued response")
            return self._poll(candidate_id, document_id, queued)
        if status not in {None, "planned"}:
            return _attempt(
                candidate_id,
                document_id,
                CaseDevPacerPurchaseStatus.UNKNOWN,
                "unreconciled_paid_outcome",
            )

        verification = self._request(
            "GET", f"/recap-documents/{_identifier(document_id)}/", {}, paid=False
        )
        _verify_recap_document(verification, document_id)
        if self.purchase_broker is None:
            raise CourtListenerRecapFetchError(
                "live RECAP Fetch is disabled until a budget-enforcing PACER "
                "credential broker is configured"
            )
        planned = self.journal.operation_evidence(document_id)
        if planned is None:
            raise CaseDevPurchaseLedgerError("planned purchase disappeared")
        submission_context = {
            "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
            "reservation_usd": str(planned["reservation_usd"]),
        }
        if not self.journal.submit(document_id, context=submission_context):
            raise CaseDevPurchaseLedgerError("submit skipped without replayable state")
        evidence = self.journal.operation_evidence(document_id)
        if evidence is None or evidence.get("operation_key") is None:
            raise CaseDevPurchaseLedgerError("submitted purchase lacks operation key")
        broker_request = {
            "request_type": "2",
            "recap_document": document_id,
            "cycle_id": self.journal.policy.cycle_id,
            "purchase_policy_sha256": self.journal.policy.policy_sha256,
            "operation_key": str(evidence["operation_key"]),
            "reservation_usd": str(evidence["reservation_usd"]),
        }
        try:
            response = self.purchase_broker.submit(broker_request)
        except ValueError as exc:
            self.journal.fail_before_dispatch(document_id, exc)
            return _attempt(
                candidate_id,
                document_id,
                CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                "purchase_broker_local_validation_failed",
            )
        except BrokerDefiniteRejection as exc:
            self.journal.fail_before_dispatch(document_id, exc)
            return _attempt(
                candidate_id,
                document_id,
                CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                f"purchase_broker_{exc.code}",
            )
        except (
            BrokerOutcomeUnknown,
            CourtListenerRecapFetchOutcomeUnknown,
            TimeoutError,
            ConnectionError,
            OSError,
        ) as exc:
            self.journal.mark_unknown(document_id, exc)
            return _attempt(
                candidate_id,
                document_id,
                CaseDevPacerPurchaseStatus.UNKNOWN,
                "purchase_outcome_unknown",
            )
        try:
            queue_id = _queue_id(response)
        except CourtListenerRecapFetchOutcomeUnknown as exc:
            self.journal.mark_unknown(document_id, exc)
            return _attempt(
                candidate_id,
                document_id,
                CaseDevPacerPurchaseStatus.UNKNOWN,
                "purchase_broker_receipt_incomplete",
            )
        if set(response) != {"id", "reservation_id"}:
            self.journal.mark_unknown(
                document_id, "purchase broker receipt contains unexpected fields"
            )
            return _attempt(
                candidate_id,
                document_id,
                CaseDevPacerPurchaseStatus.UNKNOWN,
                "purchase_broker_receipt_incomplete",
            )
        reservation_id = response.get("reservation_id")
        if not isinstance(reservation_id, str) or not reservation_id:
            self.journal.mark_unknown(
                document_id, "purchase broker omitted durable reservation ID"
            )
            return _attempt(
                candidate_id,
                document_id,
                CaseDevPacerPurchaseStatus.UNKNOWN,
                "purchase_broker_receipt_incomplete",
            )
        queued = {
            **submission_context,
            "queue_id": queue_id,
            "reservation_id": reservation_id,
        }
        self.journal.queue(document_id, response=queued)
        return self._poll(candidate_id, document_id, queued)

    def _recover_receipts(self, intended: Sequence[tuple[str, str]]) -> None:
        """Resume ambiguous broker operations through receipt lookup only."""

        if self.purchase_broker is None:
            return
        for _, document_id in intended:
            operation = self.journal.operation_evidence(document_id)
            if operation is None or operation["status"] not in {
                "submitted",
                "unknown",
                "queued",
                "confirmed",
                "failed",
            }:
                continue
            operation_key = operation.get("operation_key")
            if not isinstance(operation_key, str):
                raise CaseDevPurchaseLedgerError(
                    "reserved operation lacks operation key"
                )
            try:
                receipt = self.purchase_broker.receipt(operation_key)
            except BrokerDefiniteRejection as exc:
                raise CourtListenerRecapFetchError(
                    f"purchase broker rejected receipt recovery: {exc.code}"
                ) from exc
            except (BrokerOutcomeUnknown, CourtListenerRecapFetchOutcomeUnknown):
                continue
            self.apply_broker_receipt(document_id, receipt)

    def apply_broker_receipt(
        self, document_id: str, receipt: Mapping[str, Any]
    ) -> None:
        """Bind, preserve, and apply one authoritative broker receipt."""

        validated = validate_broker_receipt(receipt)
        operation = self.journal.operation_evidence(document_id)
        if operation is None:
            raise CaseDevPurchaseLedgerError("broker receipt operation is missing")
        expected = {
            "operation_key": operation.get("operation_key"),
            "cycle_id": self.journal.policy.cycle_id,
            "purchase_policy_sha256": self.journal.policy.policy_sha256,
            "recap_document": document_id,
            "case_id": operation.get("candidate_id"),
            "reservation_usd": operation.get("reservation_usd"),
        }
        if any(validated[field] != value for field, value in expected.items()):
            raise CourtListenerRecapFetchOutcomeUnknown(
                "broker receipt does not bind to the local operation"
            )
        response = operation.get("response")
        durable: Mapping[str, Any] = (
            cast(Mapping[str, Any], response) if isinstance(response, Mapping) else {}
        )
        raw_reservation_id = durable.get("reservation_id")
        if raw_reservation_id is not None and not isinstance(raw_reservation_id, str):
            raise CaseDevPurchaseLedgerError(
                "local broker reservation identity is invalid"
            )
        local_reservation_id = raw_reservation_id
        if (
            local_reservation_id is not None
            and validated["reservation_id"] != local_reservation_id
        ):
            raise CourtListenerRecapFetchOutcomeUnknown(
                "broker receipt reservation identity conflicts with the local journal"
            )
        raw_queue_id = durable.get("queue_id")
        if raw_queue_id is not None and not isinstance(raw_queue_id, str):
            raise CaseDevPurchaseLedgerError("local broker queue identity is invalid")
        local_queue_id = raw_queue_id
        receipt_queue_id = cast(str | None, validated["id"])
        if (
            local_queue_id is not None
            and receipt_queue_id is not None
            and receipt_queue_id != local_queue_id
        ):
            raise CourtListenerRecapFetchOutcomeUnknown(
                "broker receipt queue identity conflicts with the local journal"
            )
        self.journal.record_broker_receipt(document_id, validated)
        state = validated["state"]
        if state in {"queued", "delivered_but_unreconciled"}:
            if operation["status"] in {"submitted", "unknown"}:
                self.journal.recover_broker_queue(
                    document_id,
                    queue_id=str(validated["id"]),
                    reservation_id=str(validated["reservation_id"]),
                )
            return
        if state == "failed":
            if validated["billing_evidence"] is not None:
                self.journal.reconcile(
                    broker_reconciliation_record(validated, download_url=None)
                )
            return
        if state != "confirmed":
            return
        unknown_material = operation.get("material_authority") == (
            "unknown_status_attempt"
        )
        if unknown_material:
            billing_evidence = _mapping(
                validated.get("billing_evidence"), "broker billing evidence"
            )
            evidence_sha256 = str(billing_evidence.get("evidence_sha256", ""))
            operation_key = str(validated["operation_key"])
            self.journal.reconcile_unknown_broker_billing(
                document_id,
                actual_usd=str(validated["authoritative_fee_usd"]),
                evidence_sha256=evidence_sha256,
                source_reference=(
                    f"recap-fetch-broker:{operation_key}:{evidence_sha256}"
                ),
            )
        effective_queue_id = receipt_queue_id or local_queue_id
        if effective_queue_id is None:
            return
        queue_id = _identifier(str(effective_queue_id))
        queue = self._request(
            "GET", f"/recap-fetch/{queue_id}/", {}, paid=False, retry=True
        )
        if _status(queue) != 2:
            return
        document = self._request(
            "GET",
            f"/recap-documents/{_identifier(document_id)}/",
            {},
            paid=False,
            retry=True,
        )
        _verify_recap_document(document, document_id)
        if document.get("is_available") is not True:
            return
        download_url = _verified_download(document, document_id)
        if unknown_material:
            self.journal.mark_material_available_for_quarantine(
                document_id,
                provider_detail_sha256=_sha256_json(document),
                queue_response_sha256=_sha256_json(queue),
                download_url_sha256=hashlib.sha256(
                    download_url.encode("utf-8")
                ).hexdigest(),
            )
            return
        self.journal.reconcile(
            broker_reconciliation_record(validated, download_url=download_url)
        )

    def _poll(
        self,
        candidate_id: str,
        document_id: str,
        queued: Mapping[str, Any],
    ) -> CaseDevPacerPurchaseAttempt:
        queue_id = _identifier(str(queued.get("queue_id", "")))
        last_status: int | None = None
        for index in range(self.poll_attempts):
            payload = self._request(
                "GET", f"/recap-fetch/{queue_id}/", {}, paid=False, retry=True
            )
            last_status = _status(payload)
            if last_status == 2:
                document = self._request(
                    "GET",
                    f"/recap-documents/{_identifier(document_id)}/",
                    {},
                    paid=False,
                    retry=True,
                )
                verified = _verified_download(document, document_id)
                operation = self.journal.operation_evidence(document_id)
                if operation is None:
                    raise CaseDevPurchaseLedgerError(
                        "queued purchase disappeared during polling"
                    )
                if operation.get("material_authority") == "unknown_status_attempt":
                    self.journal.mark_material_available_for_quarantine(
                        document_id,
                        provider_detail_sha256=_sha256_json(document),
                        queue_response_sha256=_sha256_json(payload),
                        download_url_sha256=hashlib.sha256(
                            verified.encode("utf-8")
                        ).hexdigest(),
                    )
                    return _attempt(
                        candidate_id,
                        document_id,
                        CaseDevPacerPurchaseStatus.QUARANTINED,
                        "unknown_status_material_available_only_in_quarantine",
                    )
                confirmed = {
                    **dict(queued),
                    "queue_id": queue_id,
                    "queue_response": dict(payload),
                    "download_url": verified,
                    "reservation_usd": str(operation["reservation_usd"]),
                    "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
                }
                self.journal.confirm_reserved(document_id, response=confirmed)
                return _purchased_attempt(candidate_id, document_id, confirmed)
            if last_status in _TERMINAL_FAILURES:
                error = CourtListenerRecapFetchError(
                    f"RECAP Fetch terminal queue status {last_status}"
                )
                self.journal.fail(document_id, error)
                return _attempt(
                    candidate_id,
                    document_id,
                    CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                    f"recap_fetch_status_{last_status}",
                )
            if last_status not in {1, 4, 5}:
                self.journal.mark_unknown(
                    document_id, f"unknown RECAP Fetch status {last_status}"
                )
                return _attempt(
                    candidate_id,
                    document_id,
                    CaseDevPacerPurchaseStatus.UNKNOWN,
                    "unknown_recap_fetch_status",
                )
            if index + 1 < self.poll_attempts and self.poll_backoff_seconds:
                time.sleep(self.poll_backoff_seconds)
        return _attempt(
            candidate_id,
            document_id,
            CaseDevPacerPurchaseStatus.NOT_ATTEMPTED,
            f"recap_fetch_queued_status_{last_status}",
        )

    def _request(
        self,
        method: str,
        path: str,
        form: Mapping[str, str],
        *,
        paid: bool,
        retry: bool = False,
    ) -> Mapping[str, Any]:
        maximum = 3 if retry and not paid else 1
        for attempt in range(maximum):
            try:
                if self.before_request is not None:
                    self.before_request(method, path)
                self.courtlistener_request_count += 1
                response = self.transport.request(
                    method=method,
                    path=path,
                    form=form,
                    headers={
                        "Authorization": f"Token {self.config.api_token}",
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    timeout_seconds=self.config.timeout_seconds,
                )
            except CourtListenerRecapFetchOutcomeUnknown:
                if retry and not paid and attempt + 1 < maximum:
                    continue
                raise
            if 200 <= response.status_code < 300:
                return response.payload
            if response.status_code in _RETRYABLE and attempt + 1 < maximum:
                continue
            if paid and response.status_code in _RETRYABLE | {301, 302, 303, 307, 308}:
                raise CourtListenerRecapFetchOutcomeUnknown(
                    f"paid RECAP Fetch returned ambiguous HTTP {response.status_code}"
                )
            raise CourtListenerRecapFetchError(
                f"CourtListener returned HTTP {response.status_code}"
            )
        raise AssertionError("unreachable")


def public_documents_from_selection(
    selection_records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Index selection metadata, rejecting conflicting document identities."""

    indexed: dict[str, Mapping[str, Any]] = {}
    for selection in selection_records:
        documents = selection.get("documents")
        if not isinstance(documents, Sequence) or isinstance(documents, str):
            raise CourtListenerRecapFetchError("selection documents must be a list")
        for document in cast(Sequence[object], documents):
            if not isinstance(document, Mapping):
                raise CourtListenerRecapFetchError(
                    "selected document must be an object"
                )
            document_record = cast(Mapping[str, object], document)
            document_id = str(document_record.get("source_document_id", "")).strip()
            if not document_id or document_id in indexed:
                raise CourtListenerRecapFetchError(
                    "selected document IDs must be non-empty and unique"
                )
            indexed[document_id] = cast(Mapping[str, Any], document_record)
    return indexed


def _require_explicitly_public(metadata: Mapping[str, Any], document_id: str) -> None:
    explicitly_public = (
        metadata.get("redaction_or_seal_status") == "public"
        and metadata.get("is_sealed") is False
        and metadata.get("is_private") is False
    )
    if not explicitly_public:
        raise CourtListenerRecapFetchError(
            f"document {document_id} lacks accepted public/nonsealed evidence"
        )


def _require_unknown_attempt_evidence(
    metadata: Mapping[str, Any], document_id: str
) -> None:
    exact_unknown = (
        metadata.get("redaction_or_seal_status") == "unknown"
        and metadata.get("is_sealed") is None
        and metadata.get("is_private") is None
        and metadata.get("is_available") is False
        and metadata.get("availability_status") == "unavailable"
        and metadata.get("requires_paid_recovery") is True
        and metadata.get("restriction_evidence") == UNKNOWN_STATUS_EVIDENCE
    )
    incomplete_private_status = (
        metadata.get("redaction_or_seal_status") == "public"
        and metadata.get("is_sealed") is False
        and metadata.get("is_private") is None
        and metadata.get("availability_status") == "unavailable"
        and metadata.get("requires_paid_recovery") is True
        and metadata.get("restriction_evidence")
        == COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE
    )
    if not exact_unknown and not incomplete_private_status:
        raise CourtListenerRecapFetchError(
            f"document {document_id} lacks exact unknown-status attempt evidence"
        )


def _verify_recap_document(payload: Mapping[str, Any], document_id: str) -> None:
    actual = str(payload.get("id", ""))
    if actual != document_id:
        raise CourtListenerRecapFetchError(
            f"RECAP document identity mismatch: expected {document_id}, got {actual}"
        )
    for field_name in ("is_sealed", "is_private"):
        value = payload.get(field_name)
        if value is not None and not isinstance(value, bool):
            raise CourtListenerRecapFetchError(
                f"provider reports malformed restriction field: {field_name}"
            )
        if value is True:
            raise CourtListenerRecapFetchError("provider reports restricted document")


def _verified_download(payload: Mapping[str, Any], document_id: str) -> str:
    _verify_recap_document(payload, document_id)
    if payload.get("is_available") is not True:
        raise CourtListenerRecapFetchError("purchased RECAP document is unavailable")
    value = payload.get("filepath_local", payload.get("download_url"))
    if not isinstance(value, str) or not value.strip():
        raise CourtListenerRecapFetchError("purchased document lacks a download URL")
    url = urllib.parse.urljoin("https://www.courtlistener.com", value)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "www.courtlistener.com",
        "storage.courtlistener.com",
    }:
        raise CourtListenerRecapFetchError("purchased document URL is not allowlisted")
    if parsed.username is not None or parsed.password is not None:
        raise CourtListenerRecapFetchError(
            "purchased document URL must not contain credentials"
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise CourtListenerRecapFetchError(
            "purchased document URL has an invalid port"
        ) from exc
    if port not in {None, 443}:
        raise CourtListenerRecapFetchError(
            "purchased document URL must use the default HTTPS port"
        )
    return url


def verified_recap_download_url(payload: Mapping[str, Any], document_id: str) -> str:
    """Return an ephemeral allowlisted URL for exact available public material."""

    return _verified_download(payload, document_id)


def _purchased_attempt(
    candidate_id: str, document_id: str, response: Mapping[str, Any]
) -> CaseDevPacerPurchaseAttempt:
    reservation = str(response.get("reservation_usd", ""))
    download_url = response.get("download_url")
    if not reservation or not isinstance(download_url, str):
        raise CourtListenerRecapFetchError("confirmed response is incomplete")
    raw_actual = response.get("actual_fees")
    actual = (
        cast(Mapping[str, Any], raw_actual) if isinstance(raw_actual, Mapping) else None
    )
    pacer_fees = (
        {str(key): str(value) for key, value in actual.items()}
        if actual is not None
        else {
            "pacer_fee_usd": reservation,
            "service_fee_usd": "0.00",
            "total_usd": reservation,
            "cost_basis": "worst_case_reservation",
        }
    )
    return CaseDevPacerPurchaseAttempt(
        candidate_id=candidate_id,
        source_document_id=document_id,
        status=CaseDevPacerPurchaseStatus.PURCHASED,
        reason=(
            "confirmed_with_authoritative_fee_reconciliation"
            if actual is not None
            else "confirmed_with_worst_case_reservation_pending_fee_reconciliation"
        ),
        fee_acknowledged=True,
        pacer_fees=pacer_fees,
        download_url=download_url,
        source_provider=COURTLISTENER_RECAP_FETCH_PROVIDER,
    )


def _attempt(
    candidate_id: str,
    document_id: str,
    status: CaseDevPacerPurchaseStatus,
    reason: str,
) -> CaseDevPacerPurchaseAttempt:
    return CaseDevPacerPurchaseAttempt(
        candidate_id=candidate_id,
        source_document_id=document_id,
        status=status,
        reason=reason,
        source_provider=COURTLISTENER_RECAP_FETCH_PROVIDER,
    )


def _queue_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("id")
    if not isinstance(value, str) or not value.isdigit() or value.startswith("0"):
        raise CourtListenerRecapFetchOutcomeUnknown(
            "paid RECAP Fetch response lacks a canonical positive queue ID"
        )
    return value


def _status(payload: Mapping[str, Any]) -> int:
    value = payload.get("status")
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _identifier(value: str) -> str:
    if not value.isdigit() or value.startswith("0"):
        raise CourtListenerRecapFetchError(
            "CourtListener identifiers must be positive canonical decimals"
        )
    return value


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CourtListenerRecapFetchError(f"{field_name} must be an object")
    return cast(Mapping[str, Any], value)


def _json_object(content: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(content or b"{}")
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CourtListenerRecapFetchError(
            "CourtListener returned invalid JSON"
        ) from exc
    return _mapping(value, "CourtListener response")


def _sha256_json(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
