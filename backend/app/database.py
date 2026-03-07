import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "/app/data/exam.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            student_id  TEXT UNIQUE NOT NULL,
            class_name  TEXT DEFAULT '',
            pinyin      TEXT DEFAULT '',
            pinyin_abbr TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS exams (
            id         TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            is_active  INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS scores (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id   TEXT NOT NULL,
            exam_id      TEXT NOT NULL,
            score        REAL NOT NULL,
            total        REAL NOT NULL,
            submitted_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(student_id, exam_id)
        );
        """)
        # 预置考试
        conn.execute("""
        INSERT OR IGNORE INTO exams (id, title) VALUES
            ('chapter1', '第一章 机器人基础测验'),
            ('chapter2', '第二章 CubeMX编程测验')
        """)
        # 预置测试学生（仅在名单为空时插入，避免覆盖正式数据）
        count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        if count == 0:
            _seed_test_students(conn)


def _seed_test_students(conn):
    """插入测试用学生名单，仅在首次初始化空数据库时调用。"""
    from pypinyin import lazy_pinyin, Style

    students = [
        ("张伟",   "20230001", "2023级软工1班"),
        ("李娜",   "20230002", "2023级软工1班"),
        ("王芳",   "20230003", "2023级软工1班"),
        ("刘洋",   "20230004", "2023级软工2班"),
        ("陈静",   "20230005", "2023级软工2班"),
        ("杨磊",   "20230006", "2023级软工2班"),
        ("赵敏",   "20230007", "2023级软工3班"),
        ("吴鹏",   "20230008", "2023级软工3班"),
        ("周欣",   "20230009", "2023级软工3班"),
        ("徐晨",   "20230010", "2023级软工3班"),
    ]
    records = []
    for name, sid, cls in students:
        pinyin = "".join(lazy_pinyin(name, style=Style.NORMAL)).lower()
        abbr   = "".join(lazy_pinyin(name, style=Style.FIRST_LETTER)).lower()
        records.append((name, sid, cls, pinyin, abbr))

    conn.executemany("""
        INSERT OR IGNORE INTO students (name, student_id, class_name, pinyin, pinyin_abbr)
        VALUES (?,?,?,?,?)
    """, records)
    print(f"[init_db] 已预置 {len(records)} 名测试学生")
