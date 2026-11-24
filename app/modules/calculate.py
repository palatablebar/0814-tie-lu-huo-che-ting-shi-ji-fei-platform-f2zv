from app.business import measured


def compute(data):
    duration, union, free, invoice = data
    counted = max(0, duration - sum(b - a for a, b in union) - free)
    first = min(counted, 60)
    second = min(max(counted - 60, 0), 60)
    third = max(counted - 120, 0)
    return measured(
        first + second * 3 + third * 5,
        invoice,
        "分",
        {
            "billable_min": counted,
            "tier_1_min": first,
            "tier_2_min": second,
            "tier_3_min": third,
        },
    )
