import random
import unittest

from model import BASE_RATE, estimate, export_estimates, parse_draws, recommend


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


if __name__ == '__main__':
    unittest.main()
