from app.business import DomainIssue, by_kind, prepared, single


def prepare(rows):
    from app.business import intervals

    stay, invoice = single(rows, "stay"), single(rows, "invoice")
    left, right = stay["start_min"], stay["end_min"]
    if left >= right:
        raise DomainIssue("INVALID_STAY")
    pauses = by_kind(rows, "pause")
    if any(r["start_min"] >= r["end_min"] for r in pauses):
        raise DomainIssue("INVALID_PAUSE")
    union = intervals(
        (max(left, r["start_min"]), min(right, r["end_min"])) for r in pauses
    )
    return prepared(
        len(union),
        {"paused_min": sum(b - a for a, b in union)},
        (right - left, union, stay["free_min"], invoice["amount_cents"]),
    )
