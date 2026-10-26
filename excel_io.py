"""Excel workbook input and output. Never evaluate workbook formulas."""
from pathlib import Path

from openpyxl import Workbook, load_workbook
from model import BASE_RATE, parse_draws

HEADERS = ['회차', '번호1', '번호2', '번호3', '번호4', '번호5', '번호6']


def read_draws(path):
    if Path(path).suffix.lower() != '.xlsx':
        raise ValueError('Excel 통합 문서(.xlsx)를 선택하세요. .xls는 Excel에서 .xlsx로 저장하세요.')
    try:
        book = load_workbook(path, read_only=True, data_only=False)
    except Exception as exc:
        raise ValueError('엑셀 파일을 읽을 수 없습니다. 암호가 없는 정상 .xlsx 파일인지 확인하세요.') from exc
    try:
        sheet = book.active
        lines = []
        first = True
        for row in sheet.iter_rows():
            values = [cell.value for cell in row]
            while values and values[-1] is None:
                values.pop()
            if not values:
                continue
            if first:
                first = False
                header = [str(v).strip().lower() for v in values]
                if header in [HEADERS, HEADERS[1:], ['draw'] + [f'n{i}' for i in range(1, 7)],
                              [f'n{i}' for i in range(1, 7)]]:
                    continue
            if len(values) not in (6, 7):
                raise ValueError(f'{row[0].row}행: 본번호 6개 또는 회차 + 본번호 6개만 넣으세요. 보너스·날짜 열은 제외하세요.')
            numbers = []
            for value in values:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not float(value).is_integer():
                    raise ValueError(f'{row[0].row}행: 모든 데이터 셀은 정수여야 합니다. 빈 셀·수식·문자를 제거하세요.')
                numbers.append(int(value))
            lines.append(','.join(map(str, numbers)))
            if len(lines) > 412:
                raise ValueError('412회를 초과했습니다. 최근 412회만 남겨 주세요.')
        draws, ids = parse_draws('\n'.join(lines))
        return draws, ids, sheet.title
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('엑셀 시트 데이터를 읽을 수 없습니다. 파일을 다시 저장한 후 열어 주세요.') from exc
    finally:
        book.close()


def write_template(path):
    book = Workbook()
    sheet = book.active
    sheet.title = '최근412회'
    sheet.append(HEADERS)
    sheet.freeze_panes = 'B2'
    for column in 'ABCDEFG':
        sheet.column_dimensions[column].width = 14
    sheet.auto_filter.ref = 'A1:G413'
    book.save(path)
    book.close()


def write_analysis(path, estimates, numbers, ids, strength, uncertainty):
    book = Workbook()
    summary = book.active
    summary.title = '추천결과'
    summary.append(['항목', '값'])
    summary.append(['대상 회차', max(ids) + 1 if ids else '회차 미확인'])
    summary.append(['입력 범위', f'{min(ids)}~{max(ids)}' if ids else '회차 없음'])
    summary.append(['사전 강도', strength])
    summary.append(['사후 불확실성 반영', '예' if uncertainty else '아니오'])
    summary.append(['추천 번호'] + list(numbers))
    summary.append(['모델', 'Beta–Binomial 주변 사후근사 + 순차 가중 비복원추출'])
    summary.append(['주의', '추정 포함확률은 최종 추출 포함확률과 다름. 당첨 우위 미입증.'])
    sheet = book.create_sheet('번호별분석')
    sheet.append(['번호', '출현횟수', '사후 포함확률 추정', '균등 대비(%p)', '사후 표준편차(%p)'])
    for e in estimates:
        sheet.append([e.number, e.count, e.mean, 100 * (e.mean - BASE_RATE), 100 * e.sd])
        sheet.cell(sheet.max_row, 3).number_format = '0.000%'
    sheet.freeze_panes = 'A2'
    for ws in book:
        for col in 'ABCDEFG':
            ws.column_dimensions[col].width = 26
    book.save(path)
    book.close()
