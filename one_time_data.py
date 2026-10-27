"""Fixed, integrity-checked 836–1247 history for the separate 1248 build."""
import hashlib
import json
from datetime import date
from pathlib import Path
from excel_io import DrawInput

EXPECTED_SHA256 = 'b96e4e7e6cf160c6aa10ba73c721cd967af9b77834db99835093a973a4f94ff5'


def load_embedded_data():
    content = (Path(__file__).resolve().parent / 'embedded' / 'draws_836_1247.json').read_bytes()
    if hashlib.sha256(content).hexdigest() != EXPECTED_SHA256:
        raise ValueError('내장 데이터 검증에 실패했습니다.')
    payload = json.loads(content)
    rows = payload['draws']
    ids = [row['draw'] for row in rows]
    draws = [tuple(row['numbers']) for row in rows]
    dates = [date.fromisoformat(row['date']) for row in rows]
    if payload['target_draw'] != 1248 or ids != list(range(836, 1248)):
        raise ValueError('내장 회차 범위가 올바르지 않습니다.')
    if any(len(row) != 6 or len(set(row)) != 6 or any(not 1 <= n <= 45 for n in row) for row in draws):
        raise ValueError('내장 번호가 올바르지 않습니다.')
    return DrawInput(draws, ids, dates, '내장 836~1247회', len(rows))
