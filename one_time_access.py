"""Account-local two-launch limit with atomic SQLite persistence."""
import hashlib
import hmac
import os
from pathlib import Path
import re
import sqlite3
from datetime import date

APP_ID = 'OneTimeLottoGeneratorForYou1248'
PASSWORD_SHA256 = '7c2a0b7d94dfbc4dab636cdfd083f4a754143cc4d711f8278b45d9097eb1e846'
MAX_LAUNCHES = 2
BLOCKED_MESSAGE = '더 이상 실행할 수 없습니다.'
LAST_ALLOWED_DATE = date(2026, 10, 31)
EXPIRED_MESSAGE = '실행할 수 있는 기한이 지났습니다.'


class LicenseExpired(Exception):
    pass


def current_local_date():
    return date.today()


def ensure_not_expired(today=None):
    # Inclusive through October 31, using the computer's own local date.
    if (current_local_date() if today is None else today) > LAST_ALLOWED_DATE:
        raise LicenseExpired(EXPIRED_MESSAGE)


class LaunchLimitReached(Exception):
    pass


class AccessStateError(Exception):
    pass


def password_matches(value):
    return (isinstance(value, str) and re.fullmatch(r'[0-9]{5}', value) is not None
            and hmac.compare_digest(hashlib.sha256(value.encode('ascii')).hexdigest(), PASSWORD_SHA256))


def default_state_path():
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    return base / APP_ID / 'usage.sqlite3'


class LaunchLimiter:
    """All EXE copies in one Windows profile share this application ID/path.

    This is a local convenience restriction, not tamper-proof DRM. Deleting or
    replacing profile state, or using a different account, can bypass it.
    """
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_state_path()

    def _transaction(self, consume):
        ensure_not_expired()
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
            connection.execute('BEGIN IMMEDIATE')
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            if version == 0:
                # A nonempty/unrecognized existing DB must never reset the counter.
                tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if tables:
                    raise AccessStateError('실행 기록 형식을 확인할 수 없습니다.')
                connection.execute('CREATE TABLE usage (id INTEGER PRIMARY KEY CHECK(id=1), launches INTEGER NOT NULL CHECK(launches BETWEEN 0 AND 2))')
                connection.execute('INSERT INTO usage VALUES (1, 0)')
                connection.execute('PRAGMA user_version=1')
            elif version != 1:
                raise AccessStateError('실행 기록 버전이 올바르지 않습니다.')
            rows = connection.execute('SELECT id, launches FROM usage').fetchall()
            if len(rows) != 1 or rows[0][0] != 1 or type(rows[0][1]) is not int or not 0 <= rows[0][1] <= MAX_LAUNCHES:
                raise AccessStateError('실행 기록이 올바르지 않습니다.')
            used = rows[0][1]
            if consume:
                ensure_not_expired()
                if used >= MAX_LAUNCHES:
                    raise LaunchLimitReached(BLOCKED_MESSAGE)
                used += 1
                connection.execute('UPDATE usage SET launches=? WHERE id=1', (used,))
            connection.execute('COMMIT')
            return used
        except (OSError, sqlite3.Error) as exc:
            raise AccessStateError('실행 기록을 읽거나 저장할 수 없습니다. 실행을 중단합니다.') from exc
        finally:
            if connection is not None:
                connection.close()

    def used(self):
        return self._transaction(False)

    def authenticate(self, password):
        ensure_not_expired()
        if not password_matches(password):
            return None
        return self._transaction(True)
