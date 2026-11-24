EXPECTED = {
    "0001": (1, 240, "READY"),
    "0002": (2, 0, "READY"),
    "0003": (0, None, "INVALID_STAY"),
    "0004": (0, 30, "MISMATCH"),
}
EVIDENCE = {
    "0001": {"billable_min": 120, "tier_1_min": 60, "tier_2_min": 60, "tier_3_min": 0},
    "0002": {"billable_min": 0, "tier_1_min": 0, "tier_2_min": 0, "tier_3_min": 0},
}
