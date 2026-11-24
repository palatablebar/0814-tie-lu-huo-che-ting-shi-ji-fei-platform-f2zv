# 铁路货车停时计费台

铁路货运结算员可在工作台上传来源 CSV，对照规则判断差异，按业务组签发合格记录或登记暂缓意见。

归并约定暂停段，从停时扣除后按递进档位计费。每个输入行进入逐行处置台账：坏行只挡住明确归属的业务组，无法归属或数量对不上时整批等待补齐。组裁定携带幂等键，重试不新增裁定，失败回滚旧版。

## 启动

```sh
docker compose up --build -d --wait
```

打开 <http://localhost:18308>。页面预览带异常样例。选中阶段查看计算证据，执行批次后在签批闸门开放时按组签发无争议分组，或对异常组登记暂缓，然后导出复核证据。

## 核验

```sh
docker compose exec -T app pytest -q
```

[输入字段](docs/DATA-DICTIONARY.md) · [阶段接口](docs/HTTP.md) · [操作步骤](docs/OPERATIONS.md) · [规则与测试](docs/DEPTH.md)
