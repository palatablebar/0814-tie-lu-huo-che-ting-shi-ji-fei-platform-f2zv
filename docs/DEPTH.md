# 铁路货车停时计费台规则登记

- 规模：中型

## 功能模块

| 模块 | 动作 | 接口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 样例采信 | 预览并定位坏行 | `POST /api/stages/intake` | `app/intake/service.py` | `tests/test_intake.py` |
| M2 停时归并 | 检查领域约束 | `POST /api/stages/prepare` | `app/modules/prepare.py` | `tests/test_prepare.py` |
| M3 阶梯计费 | 查看业务计算结果 | `POST /api/stages/calculate` | `app/modules/calculate.py` | `tests/test_calculate.py` |
| M4 账款复核 | 查看签收判定 | `POST /api/stages/policy` | `app/modules/policy.py` | `tests/test_policy.py` |
| M5 运行对账 | 对照输入、采信和隔离行 | `POST /api/stages/balance` | `app/modules/reconcile.py` | `tests/test_reconcile.py` |
| M5b 按组签批判定 | 逐行台账、归属与闸门 | `POST /api/stages/balance`（`signoff` 字段） | `app/modules/signoff.py` | `tests/test_signoff.py` |
| M6 批次复核 | 执行批次并签发或暂缓 | `POST /api/runs、PATCH /api/runs/<id>` | `app/review/service.py` | `tests/test_review.py` |
| M6b 按组裁定 | 幂等签发/暂缓单个业务组 | `POST /api/runs/<id>/decisions` | `app/review/service.py、app/review/store.py` | `tests/test_decisions.py、tests/test_decisions_http.py` |
| M7 证据交付 | 下载复核清单 | `GET /api/runs/<id>/evidence` | `app/evidence/render.py` | `tests/test_evidence.py` |

## 输入陷阱

| 编号 | 规则 | 处理 | 测试 |
|---|---|---|---|
| TRAP-02 | 去除 BOM | `app/intake/reader.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-03 | 按逻辑记录读取引号内换行 | `app/intake/reader.py` | `tests/test_intake.py::test_quoted_newline_is_one_logical_record` |
| TRAP-04 | 重复表头计入忽略行 | `app/intake/service.py` | `tests/test_intake.py::test_repeated_header_is_counted` |
| TRAP-05 | 异常列数隔离 | `app/intake/schema.py` | `tests/test_intake.py::test_extra_column_is_isolated` |
| TRAP-06 | 归一化全角数字和千分位 | `app/intake/numeric.py` | `tests/test_intake.py::test_full_width_and_grouping_are_canonical` |
| TRAP-07 | 空值行隔离 | `app/intake/numeric.py` | `tests/test_intake.py::test_sentinel_keeps_row_out_of_total` |
| TRAP-08 | 记录键保留前导零 | `app/intake/schema.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-14 | 冲突版本都进入隔离 | `app/intake/resolve.py` | `tests/test_intake.py::test_duplicate_conflict_removes_both_copies` |
| TRAP-16 | 引号未闭合时拒收文件 | `app/intake/reader.py` | `tests/test_intake.py::test_unclosed_quote_invalidates_source` |
| TRAP-18 | 区分空文件、全空白和仅表头 | `app/intake/reader.py` | `tests/test_intake.py::test_empty_states_have_distinct_causes` |
| TRAP-26 | 拒绝旧版本复核 | `app/review/store.py` | `tests/test_review.py::test_review_optimistic_lock` |

## 按组签批规则

- 处置台账覆盖每个输入行（含空白行、重复表头、回放、冲突与字段坏行），条目号按源行号唯一，条目携带处置码、原因码与来源文件 SHA-256，任何输入行都不得丢失。
- 隔离行的业务组编号命中已采信组集合时标记为可归属，只挡住该组；命中不到时计入 `gate.unattributed`，整批闸门关闭。
- 闸门还要求台账行数等于输入行数、采信行数等于各组采用记录数之和；数量对不上返回 `LEDGER_MISMATCH`，整批等待补齐。
- 组资格：业务判定 `READY` 且无归属隔离行才可签发；不具备资格的组仍可登记暂缓。
- 组裁定单事务提交：修订号更新与裁定插入同成败，失败回滚旧版；`(run_id, case_id)` 唯一保证每组一条裁定，`(run_id, idempotency_key)` 唯一保证同键重试幂等。
- 裁定冻结当时的采用范围（行号、记录键、来源哈希），证据包 `review-evidence/2` 可同时复核组状态、范围与异常去向。

## 领域反例

停时按左闭右开分钟段记录。先剪裁并合并暂停时段，再扣除免计分钟。前 60 分钟每分 1 分钱，后 60 分钟每分 3 分钱，余下每分 5 分钱。

逐组预期结论见 `tests/test_policy.py`，计算过程证据见 `tests/test_calculate.py`。
