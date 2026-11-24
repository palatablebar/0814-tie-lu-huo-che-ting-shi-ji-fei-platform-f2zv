import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.business import DomainIssue

SCHEMA = """CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, report TEXT NOT NULL, created TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', revision INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '', reviewed TEXT
);
CREATE TABLE IF NOT EXISTS group_decisions (
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    decided TEXT NOT NULL,
    revision INTEGER NOT NULL,
    scope TEXT NOT NULL,
    PRIMARY KEY (run_id, case_id),
    UNIQUE (run_id, idempotency_key)
);"""


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
            db.row_factory = sqlite3.Row
            db.executescript(SCHEMA)
            yield db

    def register(self, run_id, report):
        with self.connect() as db:
            db.execute(
                "INSERT INTO runs(id,report,created) VALUES (?,?,?) ON CONFLICT(id) DO NOTHING",
                (
                    run_id,
                    json.dumps(report, ensure_ascii=False),
                    report["manifest"]["created"],
                ),
            )
        return self.load(run_id)

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise DomainIssue("RUN_NOT_FOUND")
            decisions = [
                dict(r)
                for r in db.execute(
                    "SELECT case_id,status,note,idempotency_key,decided,revision,scope "
                    "FROM group_decisions WHERE run_id=? ORDER BY decided,case_id",
                    (run_id,),
                )
            ]
        result = dict(row)
        result["report"] = json.loads(result["report"])
        for item in decisions:
            item["scope"] = json.loads(item["scope"])
        result["group_decisions"] = decisions
        return result

    def list(self):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,created,status,revision,note FROM runs ORDER BY created DESC,id LIMIT 50"
                )
            ]

    def revise(self, run_id, revision, status, note, now):
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE runs SET status=?,note=?,reviewed=?,revision=revision+1 WHERE id=? AND revision=?",
                (status, note, now, run_id, revision),
            )
            if cursor.rowcount != 1:
                raise DomainIssue("STALE_REVIEW")
        return self.load(run_id)

    def decide_group(self, run_id, case_id, status, note, key, decided, scope, revision):
        """单事务落一组裁定。

        全部校验与写入在同一事务内完成：任何一步失败都由 ``with db`` 回滚，
        旧版裁定与批次修订号保持不变。返回该组已存在的幂等记录（若有）。
        """
        scope_text = json.dumps(scope, ensure_ascii=False, sort_keys=True)
        with self.connect() as db:
            existing = db.execute(
                "SELECT * FROM group_decisions WHERE run_id=? AND idempotency_key=?",
                (run_id, key),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            cursor = db.execute(
                "UPDATE runs SET revision=revision+1, reviewed=? WHERE id=? AND revision=?",
                (decided, run_id, revision),
            )
            if cursor.rowcount != 1:
                raise DomainIssue("STALE_REVIEW")
            try:
                db.execute(
                    "INSERT INTO group_decisions"
                    "(run_id,case_id,status,note,idempotency_key,decided,revision,scope)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        case_id,
                        status,
                        note,
                        key,
                        decided,
                        revision + 1,
                        scope_text,
                    ),
                )
            except sqlite3.IntegrityError as error:
                # UNIQUE(run_id, case_id)：该组已有裁定
                raise DomainIssue("GROUP_FINALIZED") from error
        return None
