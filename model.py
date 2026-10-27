"""Bayesian marginal inclusion estimates and sequential weighted sampling."""
import csv
import io
import math
import random
import re
import heapq
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
    if len(rows) < REQUIRED_DRAWS:
        raise ValueError(f'최소 {REQUIRED_DRAWS}회가 필요합니다. 현재 {len(rows)}회입니다.')
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


@dataclass(frozen=True)
class Recommendation:
    numbers: tuple
    probability: float
    composition: tuple = ()
    subcomposition: tuple = ()


def subset_probability(weights, indices):
    """Exact unordered PL probability, summing all 6! draw orders via subset DP.

    This is a probability under the fitted recommendation model, not a proven
    probability of winning the real lottery.
    """
    selected = sorted(weights[i] for i in indices)
    total = math.fsum(weights)
    size = 1 << len(selected)
    sums = [0.0] * size
    dp = [0.0] * size
    dp[0] = 1.0
    for mask in range(1, size):
        bit = mask & -mask
        sums[mask] = sums[mask ^ bit] + selected[bit.bit_length() - 1]
    for mask in range(size - 1):
        denominator = total - sums[mask]
        for i, weight in enumerate(selected):
            bit = 1 << i
            if not mask & bit:
                dp[mask | bit] += dp[mask] * weight / denominator
    return dp[-1]


def top_recommendations(estimates, count=5):
    """Deterministic exact top-k unordered PL sets with posterior-mean weights.

    Sorted-weight subsets form a monotone lattice: replacing a selected weight
    with a smaller unselected weight cannot increase its PL probability. A
    best-first heap therefore visits globally highest-probability sets first.
    All results are distinct sets; individual numbers may repeat across sets.
    """
    ordered = sorted(estimates, key=lambda e: (-e.mean, e.number))
    if len(ordered) < 6 or not 1 <= count <= math.comb(len(ordered), 6):
        raise ValueError('6개 이상 후보와 유효한 세트 수가 필요합니다.')
    if len({e.number for e in ordered}) != len(ordered):
        raise ValueError('후보 번호는 서로 달라야 합니다.')
    weights = [e.mean for e in ordered]
    if any(not math.isfinite(w) or w <= 0 for w in weights):
        raise ValueError('추정 가중치는 유한한 양수여야 합니다.')
    first = tuple(range(6))
    frontier = [(-subset_probability(weights, first), first)]
    seen = {first}
    results = []
    while len(results) < count:
        negative_probability, indices = heapq.heappop(frontier)
        results.append(Recommendation(tuple(sorted(ordered[i].number for i in indices)),
                                      -negative_probability))
        for position in range(6):
            candidate = list(indices)
            candidate[position] += 1
            if candidate[position] >= (indices[position + 1] if position < 5 else len(ordered)):
                continue
            candidate = tuple(candidate)
            if candidate not in seen:
                seen.add(candidate)
                heapq.heappush(frontier, (-subset_probability(weights, candidate), candidate))
    return results


SUBCOMPOSITION_PLAN = (
    ((0, 1, 1), (0, 1, 1), (0, 1, 1)),
    ((1, 0, 1), (1, 0, 1), (0, 1, 1)),
    ((0, 2, 1), (0, 0, 1), (1, 1, 0)),
    ((1, 1, 1), (0, 1, 0), (1, 0, 1)),
    ((1, 1, 0), (0, 0, 1), (1, 1, 1)),
)
COMPOSITION_PLAN = tuple(tuple(sum(group) for group in plan) for plan in SUBCOMPOSITION_PLAN)
OUTPUT_SUBCOMPOSITION_PLAN = tuple(plan for plan in SUBCOMPOSITION_PLAN for _ in range(2))
OUTPUT_COMPOSITION_PLAN = tuple(tuple(sum(group) for group in plan) for plan in OUTPUT_SUBCOMPOSITION_PLAN)
SET_COUNT = len(OUTPUT_SUBCOMPOSITION_PLAN)


def passes_pattern_rules(numbers):
    """Reject n,n+1,n+2 and n,n+7,n+14 anywhere within one set."""
    selected = set(numbers)
    return not any(n + step in selected and n + 2 * step in selected
                   for n in selected for step in (1, 7))


def frequency_groups(estimates):
    """Partition 45 numbers by historical count into high/middle/low 15s."""
    if len(estimates) != 45 or {e.number for e in estimates} != set(range(1, 46)):
        raise ValueError('빈도 그룹 분류에는 1~45의 번호별 추정값이 필요합니다.')
    ordered = sorted(estimates, key=lambda e: (-e.count, e.number))
    return tuple(tuple(e.number for e in ordered[start:start + 15]) for start in (0, 15, 30))


def frequency_subgroups(estimates):
    """Split each 15-number group into weight-ranked high/middle/low fives."""
    lookup = {e.number: e for e in estimates}
    return tuple(tuple(tuple(ordered[start:start + 5]) for start in (0, 5, 10))
                 for group in frequency_groups(estimates)
                 for ordered in [sorted(group, key=lambda n: (-lookup[n].mean, n))])


def top_composition_recommendations(estimates, groups, composition, count, rng=None, predicate=None):
    """Exact top-k PL sets within a fixed high/middle/low composition.

    Each group's sorted-index subset lattice is monotone. Best-first traversal
    of their Cartesian product gives exact constrained top-k without sampling.
    Raw PL probabilities suffice for ranking within one composition; no claim
    is made that different composition quotas follow an optimum portfolio.
    """
    if not groups or len(groups) != len(composition) or sum(composition) != 6:
        raise ValueError('그룹과 구성의 개수가 같고 선택 개수의 합은 6이어야 합니다.')
    lookup = {e.number: e for e in estimates}
    numbers = [n for group in groups for n in group]
    if len(lookup) != len(estimates) or len(set(numbers)) != len(numbers) or set(numbers) != set(lookup):
        raise ValueError('빈도 그룹은 모든 후보 번호를 중복 없이 포함해야 합니다.')
    available = 1
    ordered = []
    for group, quota in zip(groups, composition):
        if not isinstance(quota, int) or not 0 <= quota <= len(group):
            raise ValueError('빈도 그룹 크기보다 많은 번호를 선택할 수 없습니다.')
        available *= math.comb(len(group), quota)
        candidates = sorted((lookup[n] for n in group), key=lambda e: e.number)
        if rng is not None:
            # Stable weight sorting preserves the shuffled order only for ties.
            # Unequal weights retain their original priority.
            rng.shuffle(candidates)
            candidates.sort(key=lambda e: -e.mean)
        else:
            candidates.sort(key=lambda e: (-e.mean, e.number))
        ordered.append(candidates)
    if not 1 <= count <= available:
        raise ValueError('해당 구성에서 만들 수 없는 세트 수입니다.')
    flat = [e for group in ordered for e in group]
    weights = [e.mean for e in flat]
    if any(not math.isfinite(w) or w <= 0 for w in weights):
        raise ValueError('추정 가중치는 유한한 양수여야 합니다.')
    offsets = []
    offset = 0
    for group in ordered:
        offsets.append(offset)
        offset += len(group)

    def flatten(state):
        return tuple(offset + i for offset, group in zip(offsets, state) for i in group)

    seed = tuple(tuple(range(quota)) for quota in composition)
    heap = [(-subset_probability(weights, flatten(seed)), seed)]
    seen = {seed}
    result = []
    while heap and len(result) < count:
        negative_probability, state = heapq.heappop(heap)
        selected_numbers = tuple(sorted(flat[i].number for i in flatten(state)))
        if predicate is None or predicate(selected_numbers):
            result.append(Recommendation(selected_numbers, -negative_probability, tuple(composition)))
        # Invalid candidates still have valid descendants; never prune them.
        for g, indices in enumerate(state):
            for position in range(len(indices)):
                next_indices = list(indices)
                next_indices[position] += 1
                limit = indices[position + 1] if position + 1 < len(indices) else len(ordered[g])
                if next_indices[position] >= limit:
                    continue
                next_state = list(state)
                next_state[g] = tuple(next_indices)
                next_state = tuple(next_state)
                if next_state not in seen:
                    seen.add(next_state)
                    heapq.heappush(heap, (-subset_probability(weights, flatten(next_state)), next_state))
    if len(result) != count:
        raise ValueError('빈도 구성과 연속 번호 제한을 모두 만족하는 조합이 부족합니다. 입력 데이터를 확인하세요.')
    return result


def balanced_recommendations(estimates, rng=None):
    rng = rng if rng is not None else random.SystemRandom()
    subgroups = frequency_subgroups(estimates)
    groups = tuple(group for parent in subgroups for group in parent)
    result = []
    lookup = {e.number: e.mean for e in estimates}
    for plan, composition in zip(SUBCOMPOSITION_PLAN, COMPOSITION_PLAN):
        quotas = tuple(quota for parent in plan for quota in parent)
        selected = top_composition_recommendations(estimates, groups, quotas, 2, rng=rng,
                                                   predicate=passes_pattern_rules)
        for candidate in selected:
            ranked_numbers = tuple(sorted(candidate.numbers, key=lambda n: (-lookup[n], n)))
            result.append(Recommendation(ranked_numbers, candidate.probability, composition, plan))
    return result
