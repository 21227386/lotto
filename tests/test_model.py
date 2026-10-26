import random
import unittest
import itertools
import math

from model import BASE_RATE, COMPOSITION_PLAN, Estimate, estimate, export_estimates, parse_draws, recommend, subset_probability, top_recommendations, frequency_groups, balanced_recommendations, top_composition_recommendations


def dataset():
    rng = random.Random(17)
    return '\n'.join(','.join(map(str, [836 + i] + rng.sample(range(1, 46), 6))) for i in range(412))


class ModelTests(unittest.TestCase):
    def test_valid_input_and_conjugate_update(self):
        draws, ids = parse_draws('draw,n1,n2,n3,n4,n5,n6\n' + dataset())
        self.assertEqual((len(draws), min(ids), max(ids)), (412, 836, 1247))
        values = estimate(draws)
        self.assertAlmostEqual(sum(e.mean for e in values), 6)
        for e in values:
            self.assertAlmostEqual(e.mean, (412 * BASE_RATE + e.count) / 824)
            self.assertLessEqual(abs(e.mean - BASE_RATE), abs(e.count / 412 - BASE_RATE) + 1e-12)

    def test_bad_inputs(self):
        data = dataset()
        for bad in [data.split('\n', 1)[1], data + '\n1,2,3,4,5,6',
                    data.replace(data.splitlines()[0], '836,1,1,2,3,4,5'),
                    data.replace('837,', '836,'), data.replace('837,', '9999,'),
                    data.replace(data.splitlines()[0], '836,0,2,3,4,5,6')]:
            with self.subTest(bad=bad[:35]), self.assertRaises(ValueError):
                parse_draws(bad)
        for strength in [0, -1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                estimate(parse_draws(data)[0], strength)

    def test_without_replacement_and_uncertainty(self):
        estimates = estimate(parse_draws(dataset())[0])
        rng = random.Random(9)
        for uncertainty in [False, True]:
            for _ in range(1000):
                numbers = recommend(estimates, uncertainty, rng)
                self.assertEqual(len(set(numbers)), 6)
                self.assertEqual(numbers, sorted(numbers))
                self.assertTrue(all(1 <= n <= 45 for n in numbers))

    def test_weights_affect_draws(self):
        estimates = estimate([(1, 2, 3, 4, 5, 6)] * 412, strength=1)
        rng = random.Random(23)
        hits = sum(len(set(recommend(estimates, rng=rng)) & set(range(1, 7))) for _ in range(500))
        self.assertGreater(hits, 2900)
        self.assertEqual(len(export_estimates(estimates).splitlines()), 46)

    def test_subset_probability_matches_all_orders(self):
        weights = [8, 7, 6, 5, 4, 3, 2, 1]
        indices = (0, 1, 2, 3, 4, 7)
        expected = 0.0
        for permutation in itertools.permutations(indices):
            remaining = sum(weights)
            probability = 1.0
            for i in permutation:
                probability *= weights[i] / remaining
                remaining -= weights[i]
            expected += probability
        self.assertAlmostEqual(subset_probability(weights, indices), expected, places=14)
        self.assertAlmostEqual(sum(subset_probability(weights, c) for c in itertools.combinations(range(8), 6)), 1.0)

    def test_exact_top_five_against_exhaustive_search(self):
        rng = random.Random(31)
        for _ in range(12):
            weights = [rng.uniform(1, 20) for _ in range(9)]
            estimates = [Estimate(i + 1, 0, w, 30 - w) for i, w in enumerate(weights)]
            results = top_recommendations(estimates)
            brute = sorted((subset_probability(weights, c) for c in itertools.combinations(range(9), 6)), reverse=True)[:5]
            self.assertEqual(len({r.numbers for r in results}), 5)
            for actual, expected in zip(results, brute):
                self.assertAlmostEqual(actual.probability, expected, places=14)
            self.assertEqual(results, top_recommendations(list(reversed(estimates))))

    def test_equal_weights_and_reproducible_results(self):
        estimates = [Estimate(i, 0, 6, 39) for i in range(1, 46)]
        results = top_recommendations(estimates)
        self.assertEqual(results[0].numbers, (1, 2, 3, 4, 5, 6))
        self.assertEqual(len({r.numbers for r in results}), 5)
        for r in results:
            self.assertAlmostEqual(r.probability, 1 / math.comb(45, 6), places=18)
        self.assertEqual(results, top_recommendations(estimates))

    def test_new_draws_are_included_in_posterior(self):
        draws = parse_draws(dataset())[0] + [(1, 2, 3, 4, 5, 6)]
        result = estimate(draws)
        self.assertEqual(sum(e.count for e in result), 413 * 6)
        self.assertAlmostEqual(result[0].mean, (412 * BASE_RATE + result[0].count) / 825)

    def test_frequency_ties_and_partition(self):
        values = [Estimate(i, 20, 6, 39) for i in range(45, 0, -1)]
        groups = frequency_groups(values)
        self.assertEqual(groups, (tuple(range(1, 16)), tuple(range(16, 31)), tuple(range(31, 46))))
        varied = estimate(parse_draws(dataset())[0])
        groups = frequency_groups(varied)
        lookup = {e.number: e.count for e in varied}
        self.assertTrue(min(lookup[n] for n in groups[0]) >= max(lookup[n] for n in groups[1]))
        self.assertTrue(min(lookup[n] for n in groups[1]) >= max(lookup[n] for n in groups[2]))

    def test_five_sets_match_requested_frequency_compositions(self):
        values = estimate(parse_draws(dataset())[0])
        groups = frequency_groups(values)
        results = balanced_recommendations(values)
        self.assertEqual(len({r.numbers for r in results}), 5)
        self.assertEqual(tuple(r.composition for r in results), COMPOSITION_PLAN)
        for r in results:
            self.assertEqual(len(set(r.numbers)), 6)
            self.assertEqual(tuple(len(set(r.numbers) & set(group)) for group in groups), r.composition)
        self.assertEqual(results, balanced_recommendations(list(reversed(values))))
        for start in (0, 2):
            self.assertGreaterEqual(results[start].probability, results[start + 1].probability)

    def test_constrained_rank_matches_exhaustive_search(self):
        rng = random.Random(75)
        groups = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
        for _ in range(5):
            weights = [rng.uniform(1, 20) for _ in range(9)]
            values = [Estimate(i + 1, 0, w, 30 - w) for i, w in enumerate(weights)]
            for composition in ((2, 2, 2), (3, 1, 2), (2, 1, 3)):
                candidates = itertools.product(*(itertools.combinations(group, quota) for group, quota in zip(groups, composition)))
                brute = sorted([subset_probability(weights, [n - 1 for group in choice for n in group])
                                for choice in candidates], reverse=True)[:2]
                results = top_composition_recommendations(values, groups, composition, 2)
                for actual, expected in zip(results, brute):
                    self.assertAlmostEqual(actual.probability, expected, places=14)


if __name__ == '__main__':
    unittest.main()
