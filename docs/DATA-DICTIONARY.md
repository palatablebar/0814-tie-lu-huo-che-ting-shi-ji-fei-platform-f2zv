# 字段与业务定义

输入编码 UTF-8，允许 BOM。首行必须匹配样例列顺序。记录键和业务组保留原始字符串。`kind` 允许 stay, pause, invoice。说明列 `note` 可以跨行，限制 200 字。

业务字段按 `start_min`、`end_min`、`free_min`、`amount_cents` 排列。数字接受非负整数、全角数字和完整千分位。空串、短横线、N/A、NULL 与未知为缺值。无关字段用 0 占位。

停时按左闭右开分钟段记录。先剪裁并合并暂停时段，再扣除免计分钟。前 60 分钟每分 1 分钱，后 60 分钟每分 3 分钱，余下每分 5 分钱。

`incoming.csv` 包含四个业务组，第二组提供不同边界，第三组触发业务拒收，第四组需要核对。另含重复表头、冲突记录、重复回放与错误列数；其中错误列数等坏行归属到不存在的 9999 组，签批闸门关闭。`attributable.csv` 的坏行全部归属到 0003 组，台账守恒、闸门开放，0001、0002 组可按期签批。`ready.csv` 含可以签发的两个组。

## 处置台账

每个输入行在 `signoff.ledger` 中恰好对应一条条目，字段为 `entry_id`（按源行号唯一）、`line`、`record`、`case`、`disposition`（`ACCEPTED`/`REJECTED`/`BLANK_LINE`/`HEADER_REPLAY`）、`reason`、`source`（来源文件 SHA-256）。隔离条目另带 `attributable` 与 `group`：可归属时指向命中的业务组，否则为 `null` 并计入闸门的不可归属清单。各组 `scope.records` 给出采用记录的行号、记录键与来源哈希，`exceptions` 给出该组隔离条目的去向（`ISOLATED`）。
