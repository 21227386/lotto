"""Bayesian marginal inclusion estimates and sequential weighted sampling."""
import csv
import io
import math
import random
import re
from dataclasses import dataclass

BASE_RATE = 6 / 45
REQUIRED_DRAWS = 412


def parse_draws(text):
    """Accept six numbers, or draw number followed by six numbers per row."""
    rows = []
    ids = []
    width = None
    for line_no, line in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        if not line.strip():
            continue
        tokens = re.split(r'[,;\t ]+', line.strip())
        try:
            values = [int(token) for token in tokens]
        except ValueError:
            # Only an explicit, documented header is accepted.
            normalized = [t.lower() for t in tokens]
            if not rows and normalized in [
                ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'],
                ['draw', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6'],
            ]:
                continue
            raise ValueError(f'{line_no}행: 정수만 입력하세요. 날짜와 보너스 번호는 제외하세요.')
        if len(values) not in (6, 7):
            raise ValueError(f'{line_no}행: 본번호 6개 또는 회차 + 본번호 6개가 필요합니다.')
        if width is not None and width != len(values):
            raise ValueError(f'{line_no}행: 모든 행의 열 개수가 같아야 합니다.')
        width = len(values)
        if width == 7:
            draw_id = values.pop(0)
            if draw_id <= 0 or draw_id in ids:
                raise ValueError(f'{line_no}행: 회차는 중복 없는 양의 정수여야 합니다.')
            ids.append(draw_id)
        if len(set(values)) != 6 or any(n < 1 or n > 45 for n in values):
            raise ValueError(f'{line_no}행: 1~45의 서로 다른 본번호 6개가 필요합니다.')
        rows.append(tuple(sorted(values)))
    if len(rows) != REQUIRED_DRAWS:
        raise ValueError(f'정확히 {REQUIRED_DRAWS}회가 필요합니다. 현재 {len(rows)}회입니다.')
    if ids and sorted(ids) != list(range(min(ids), max(ids) + 1)):
        raise ValueError('회차가 연속되지 않습니다. 누락 회차를 확인하세요.')
    return rows, ids


@dataclass(frozen=True)
class Estimate:
    number: int
    count: int
    alpha: float
    beta: float

    @property
    def mean(self):
        return self.alpha / (self.alpha + self.beta)

    @property
    def sd(self):
        a, b = self.alpha, self.beta
        return math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))


def estimate(draws, strength=412.0):
    if not math.isfinite(strength) or strength <= 0:
        raise ValueError('사전 강도는 유한한 양수여야 합니다.')
    counts = [0] * 45
    for row in draws:
        for n in row:
            counts[n - 1] += 1
    return [Estimate(i + 1, count, BASE_RATE * strength + count,
                     (1 - BASE_RATE) * strength + len(draws) - count)
            for i, count in enumerate(counts)]


def recommend(estimates, uncertainty=False, rng=None):
    """Plackett–Luce sequential draws; remove each selected ball."""
    rng = rng or random.SystemRandom()
    remaining = [(e.number, rng.betavariate(e.alpha, e.beta) if uncertainty else e.mean)
                 for e in estimates]
    result = []
    for _ in range(6):
        threshold = rng.random() * sum(w for _, w in remaining)
        cumulative = 0.0
        index = len(remaining) - 1
        for j, (_, weight) in enumerate(remaining):
            cumulative += weight
            if threshold < cumulative:
                index = j
                break
        number, _ = remaining.pop(index)
        result.append(number)
    return sorted(result)


def export_estimates(estimates):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['number', 'count', 'posterior_mean', 'posterior_sd', 'deviation_from_uniform'])
    for e in estimates:
        writer.writerow([e.number, e.count, e.mean, e.sd, e.mean - BASE_RATE])
    return out.getvalue()
