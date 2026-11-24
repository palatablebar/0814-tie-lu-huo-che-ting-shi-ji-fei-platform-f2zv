from collections import Counter
from csv import Error
from hashlib import sha256

from app.business import DomainIssue
from app.intake.reader import records
from app.intake.resolve import partition
from app.intake.schema import HEADER, record

# 处置码：台账中每个输入行恰好一种处置
ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
BLANK_LINE = "BLANK_LINE"
HEADER_REPLAY = "HEADER_REPLAY"


def inspect(data):
    source_sha = sha256(data).hexdigest()
    counted = repeated = blanks = 0
    candidates, rejected, ledger = [], [], []
    try:
        for line, values in records(data):
            counted += 1
            if not any(v.strip() for v in values):
                blanks += 1
                ledger.append(
                    dict(
                        entry_id=f"L{line}",
                        line=line,
                        record=None,
                        case=None,
                        disposition=BLANK_LINE,
                        reason="BLANK_LINE",
                        source=source_sha,
                    )
                )
                continue
            if tuple(values) == HEADER:
                repeated += 1
                ledger.append(
                    dict(
                        entry_id=f"L{line}",
                        line=line,
                        record=None,
                        case=None,
                        disposition=HEADER_REPLAY,
                        reason="HEADER_REPLAY",
                        source=source_sha,
                    )
                )
                continue
            try:
                row = record(values)
            except DomainIssue as error:
                key = values[0][:36] if values else ""
                case = values[1][:36] if len(values) > 1 else ""
                item = dict(line=line, record=key, case=case, reason=error.code)
                rejected.append(item)
                ledger.append(_entry(line, key, case, REJECTED, error.code, source_sha))
                continue
            candidates.append((line, row))
    except Error as error:
        raise DomainIssue("CSV_MALFORMED") from error
    accepted, conflicts = partition(candidates)
    for line, row in accepted:
        ledger.append(
            _entry(line, row["record"], row["case"], ACCEPTED, "ACCEPTED", source_sha)
        )
    rejects = sorted(rejected + conflicts, key=lambda row: row["line"])
    for item in conflicts:
        ledger.append(
            _entry(
                item["line"],
                item["record"],
                item["case"],
                REJECTED,
                item["reason"],
                source_sha,
            )
        )
    ledger.sort(key=lambda item: item["line"])
    accepted_rows = [row for _, row in sorted(accepted)]
    accepted_lines = {row["record"]: line for line, row in accepted}
    return dict(
        input=counted,
        accepted=len(accepted_rows),
        repeated=repeated,
        blank=blanks,
        rejected=len(rejects),
        reasons=dict(Counter(r["reason"] for r in rejects)),
        isolation=rejects,
        rows=accepted_rows,
        accepted_lines=accepted_lines,
        source_sha256=source_sha,
        ledger=ledger,
    )


def _entry(line, key, case, disposition, reason, source_sha):
    return dict(
        entry_id=f"L{line}",
        line=line,
        record=key or None,
        case=case or None,
        disposition=disposition,
        reason=reason,
        source=source_sha,
    )
