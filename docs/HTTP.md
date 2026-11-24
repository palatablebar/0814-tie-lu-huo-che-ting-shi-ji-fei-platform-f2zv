# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean`、`sample=attributable` 或 `file=<CSV>` 四选一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。`balance` 阶段额外返回 `signoff`：逐行处置台账 `ledger`、批次闸门 `gate` 与逐组签批资格 `groups`。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批、当前复核状态与逐组裁定 `group_decisions`。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。

`POST /api/runs/<id>/decisions` 按业务组下达裁定，请求体：

| 字段 | 说明 |
|---|---|
| `case` | 业务组编号 |
| `status` | `APPROVED` 或 `HELD` |
| `note` | 3 至 200 字裁定意见 |
| `revision` | 读到的批次修订号，乐观锁 |
| `idempotency_key` | 8 至 64 位字母、数字、`_`、`-`；同键重试不新增裁定 |

闸门关闭（`BATCH_GATE_CLOSED`，409）时任何组都不能裁定；组不具备资格时签发返回 `GROUP_NOT_ELIGIBLE`（409），仍可暂缓；组已有裁定返回 `GROUP_FINALIZED`（409）；修订号过期返回 `STALE_REVIEW`（409）。校验失败不写入，修订号不变。

`GET /api/runs/<id>/evidence` 下载 `review-evidence/2` JSON，内含运行清单、逐行处置台账、批次闸门、业务证据、逐组采用范围、异常去向与全部组裁定。
