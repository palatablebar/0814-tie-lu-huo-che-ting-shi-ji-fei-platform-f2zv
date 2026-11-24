from collections import defaultdict


def partition(candidates):
    """按记录键分区。

    采信项保留首次出现的源行号，返回 ``(line, row)``；隔离项仍为带行号的
    原因字典，便于处置台账逐行落账。
    """
    by_key = defaultdict(list)
    for line, row in candidates:
        by_key[row["record"]].append((line, row))
    accepted, rejected = [], []
    for key, records in by_key.items():
        first_line, first = records[0]
        if any(row != first for _, row in records):
            rejected.extend(
                {
                    "line": line,
                    "record": key,
                    "case": row["case"],
                    "reason": "DUPLICATE_CONFLICT",
                }
                for line, row in records
            )
            continue
        accepted.append((first_line, first))
        rejected.extend(
            {
                "line": line,
                "record": key,
                "case": row["case"],
                "reason": "DUPLICATE_REPLAY",
            }
            for line, row in records[1:]
        )
    return accepted, rejected
