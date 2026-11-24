COLUMNS = ("start_min", "end_min", "free_min", "amount_cents")
KINDS = ("stay", "pause", "invoice")
PROJECT = {
    "name": "铁路货车停时计费台",
    "actor": "铁路货运结算员",
    "stages": [
        ("intake", "样例采信"),
        ("prepare", "停时归并"),
        ("calculate", "阶梯计费"),
        ("policy", "账款复核"),
        ("balance", "运行对账"),
    ],
    "chart": "阶梯账款",
}
