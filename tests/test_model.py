import random
import unittest
import itertools
import math

from model import BASE_RATE, COMPOSITION_PLAN, SUBCOMPOSITION_PLAN, OUTPUT_SUBCOMPOSITION_PLAN, OUTPUT_COMPOSITION_PLAN, passes_pattern_rules, Estimate, estimate, export_estimates, parse_draws, recommend, subset_probability, top_recommendations, frequency_groups, frequency_subgroups, balanced_recommendations, top_composition_recommendations


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
        results = balanced_recommendations(values, rng=random.Random(123))
        self.assertEqual(len({r.numbers for r in results}), 10)
        self.assertEqual(tuple(r.composition for r in results), OUTPUT_COMPOSITION_PLAN)
        for r in results:
            self.assertEqual(len(set(r.numbers)), 6)
            self.assertEqual(tuple(len(set(r.numbers) & set(group)) for group in groups), r.composition)
        self.assertEqual(results, balanced_recommendations(list(reversed(values)), rng=random.Random(123)))

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

    def test_nested_subgroups_and_requested_nine_quotas(self):
        values = estimate(parse_draws(dataset())[0])
        groups = frequency_subgroups(values)
        lookup = {e.number: e.mean for e in values}
        self.assertEqual(len(groups), 3)
        for parent in groups:
            self.assertEqual([len(part) for part in parent], [5, 5, 5])
            numbers = [n for part in parent for n in part]
            self.assertEqual(numbers, sorted(numbers, key=lambda n: (-lookup[n], n)))
        results = balanced_recommendations(values)
        for result, plan in zip(results, OUTPUT_SUBCOMPOSITION_PLAN):
            self.assertEqual(result.subcomposition, plan)
            self.assertEqual(tuple(tuple(len(set(result.numbers) & set(part)) for part in parent)
                                   for parent in groups), plan)
        tied = [Estimate(i, 10, 6, 39) for i in range(1, 46)]
        self.assertEqual(frequency_subgroups(tied)[0], (tuple(range(1, 6)), tuple(range(6, 11)), tuple(range(11, 16))))

    def test_nine_group_top_choice_matches_exhaustive_search(self):
        rng = random.Random(130)
        weights = [rng.uniform(1, 20) for _ in range(18)]
        values = [Estimate(i + 1, 0, w, 30 - w) for i, w in enumerate(weights)]
        groups = tuple((2 * i + 1, 2 * i + 2) for i in range(9))
        for plan in SUBCOMPOSITION_PLAN:
            quotas = tuple(n for parent in plan for n in parent)
            candidates = itertools.product(*(itertools.combinations(group, quota) for group, quota in zip(groups, quotas)))
            expected = max(subset_probability(weights, [n - 1 for part in candidate for n in part]) for candidate in candidates)
            result = top_composition_recommendations(values, groups, quotas, 1)[0]
            self.assertAlmostEqual(result.probability, expected, places=14)

    def test_random_ties_do_not_override_unequal_weights(self):
        class ReverseShuffle:
            def shuffle(self, items):
                items.reverse()
        weights = [9, 9, 1, 8, 7, 1, 6, 5, 1]
        values = [Estimate(i + 1, 0, w, 30 - w) for i, w in enumerate(weights)]
        groups = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
        result = top_composition_recommendations(values, groups, (1, 2, 3), 1, rng=ReverseShuffle())[0]
        self.assertEqual(result.numbers, (2, 4, 5, 7, 8, 9))
        baseline = top_composition_recommendations(values, groups, (1, 2, 3), 1)[0]
        self.assertAlmostEqual(result.probability, baseline.probability)

    def test_tied_numbers_can_vary_and_repeat_between_sets(self):
        values = [Estimate(i, 50, 6, 39) for i in range(1, 46)]
        rng = random.Random(314)
        observed = []
        for _ in range(30):
            results = balanced_recommendations(values, rng=rng)
            observed.append(tuple(r.numbers for r in results))
            self.assertEqual(tuple(r.subcomposition for r in results), OUTPUT_SUBCOMPOSITION_PLAN)
            self.assertTrue(all(len(set(r.numbers)) == 6 for r in results))
        self.assertGreater(len(set(observed)), 20)
        self.assertTrue(any(len([n for row in run for n in row]) > len({n for row in run for n in row}) for run in observed))

    def test_number_pattern_rules(self):
        for invalid in [(1, 2, 3, 21, 32, 45), (1, 8, 15, 25, 34, 45), (20, 27, 34, 2, 9, 40), (43, 44, 45, 2, 12, 23)]:
            self.assertFalse(passes_pattern_rules(invalid))
        for valid in [(1, 2, 10, 11, 30, 45), (1, 8, 22, 31, 35, 44), (1, 8, 10, 17, 26, 40)]:
            self.assertTrue(passes_pattern_rules(valid))

    def test_filtered_search_matches_exhaustive_and_explores_invalid_ancestors(self):
        weights = [12, 11, 10, 9, 8, 7, 6, 5, 4]
        values = [Estimate(i + 1, 0, w, 30 - w) for i, w in enumerate(weights)]
        groups = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
        composition = (2, 2, 2)
        choices = itertools.product(*(itertools.combinations(g, q) for g, q in zip(groups, composition)))
        candidates = [tuple(n for part in c for n in part) for c in choices]
        valid = [c for c in candidates if passes_pattern_rules(c)]
        brute = sorted((subset_probability(weights, [n - 1 for n in c]) for c in valid), reverse=True)[:2]
        actual = top_composition_recommendations(values, groups, composition, 2, predicate=passes_pattern_rules)
        for r, expected in zip(actual, brute):
            self.assertTrue(passes_pattern_rules(r.numbers))
            self.assertAlmostEqual(r.probability, expected, places=14)
        impossible = [Estimate(i, 0, 6, 39) for i in range(1, 7)]
        with self.assertRaises(ValueError):
            top_composition_recommendations(impossible, ((1, 2), (3, 4), (5, 6)), (2, 2, 2), 1,
                                            predicate=passes_pattern_rules)

    def test_ten_sets_are_valid_unique_and_presented_by_weight(self):
        values = estimate(parse_draws(dataset())[0])
        lookup = {e.number: e.mean for e in values}
        results = balanced_recommendations(values, rng=random.Random(44))
        self.assertEqual(len(results), 10)
        self.assertEqual(len({tuple(sorted(r.numbers)) for r in results}), 10)
        for r in results:
            self.assertTrue(passes_pattern_rules(r.numbers))
            self.assertEqual(r.numbers, tuple(sorted(r.numbers, key=lambda n: (-lookup[n], n))))
        for i in range(0, 10, 2):
            self.assertGreaterEqual(results[i].probability, results[i + 1].probability)


if __name__ == '__main__':
    unittest.main()
