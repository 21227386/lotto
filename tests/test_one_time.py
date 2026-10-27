from contextlib import closing
import hashlib
from datetime import date
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest

from one_time_access import LaunchLimiter, LaunchLimitReached, AccessStateError, password_matches, LicenseExpired, ensure_not_expired
from one_time_data import load_embedded_data


class OneTimeTests(unittest.TestCase):
    def setUp(self):
        clock_patch = patch('one_time_access.current_local_date', return_value=date(2026, 10, 27))
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        password_patch = patch('one_time_access.PASSWORD_SHA256', hashlib.sha256(b'12345').hexdigest())
        password_patch.start()
        self.addCleanup(password_patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'profile' / 'usage.sqlite3'

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_password_and_no_charge_for_wrong_password(self):
        gate = LaunchLimiter(self.path)
        for value in ['', '00000', '1234', '123450', '１２３４５', ' 12345', None]:
            self.assertFalse(password_matches(value))
            self.assertIsNone(gate.authenticate(value))
        self.assertEqual(gate.used(), 0)
        self.assertTrue(password_matches('12345'))

    def test_one_successful_launch_then_persistent_block(self):
        self.assertEqual(LaunchLimiter(self.path).authenticate('12345'), 1)
        with self.assertRaisesRegex(LaunchLimitReached, '더 이상 실행할 수 없습니다.'):
            LaunchLimiter(self.path).authenticate('12345')
        self.assertEqual(LaunchLimiter(self.path).used(), 1)

    def test_concurrent_launches_cannot_exceed_one(self):
        def attempt(_):
            try:
                return LaunchLimiter(self.path).authenticate('12345')
            except LaunchLimitReached:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(sorted(r for r in results if r is not None), [1])
        self.assertEqual(LaunchLimiter(self.path).used(), 1)

    def test_corrupt_state_fails_closed(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b'broken database')
        with self.assertRaises(AccessStateError):
            LaunchLimiter(self.path).used()
        self.path.unlink()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA user_version=99')
        with self.assertRaises(AccessStateError):
            LaunchLimiter(self.path).authenticate('12345')

    def test_embedded_history_is_exactly_412_fixed_draws(self):
        data = load_embedded_data()
        self.assertEqual(data.ids, list(range(836, 1248)))
        self.assertEqual(len(data.draws), 412)
        self.assertEqual(data.dates[-1].isoformat(), '2026-10-24')
        self.assertEqual(data.draws[-1], (8, 14, 21, 22, 42, 45))

    def test_deadline_allows_october_31_and_blocks_november_1(self):
        ensure_not_expired(date(2026, 10, 31))
        with self.assertRaisesRegex(LicenseExpired, '실행할 수 있는 기한이 지났습니다.'):
            ensure_not_expired(date(2026, 11, 1))
        with patch('one_time_access.current_local_date', return_value=date(2026, 10, 31)):
            self.assertEqual(LaunchLimiter(self.path).authenticate('12345'), 1)
        before = self.path.read_bytes()
        with patch('one_time_access.current_local_date', return_value=date(2026, 11, 1)):
            with self.assertRaises(LicenseExpired):
                LaunchLimiter(self.path).authenticate('12345')
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(LaunchLimiter(self.path).used(), 1)

    def test_expiry_has_priority_and_does_not_create_state(self):
        with patch('one_time_access.current_local_date', return_value=date(2026, 11, 1)):
            with self.assertRaises(LicenseExpired):
                LaunchLimiter(self.path).used()
            with self.assertRaises(LicenseExpired):
                LaunchLimiter(self.path).authenticate('wrong')
        self.assertFalse(self.path.exists())
        limiter = LaunchLimiter(self.path)
        limiter.authenticate('12345')
        with patch('one_time_access.current_local_date', return_value=date(2026, 11, 1)):
            with self.assertRaises(LicenseExpired):
                limiter.authenticate('12345')

    def test_old_two_use_record_is_exhausted_without_reset(self):
        limiter = LaunchLimiter(self.path)
        limiter.authenticate('12345')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE usage SET launches=2 WHERE id=1')
            db.commit()
        self.assertEqual(limiter.used(), 2)
        with self.assertRaisesRegex(LaunchLimitReached, '더 이상 실행할 수 없습니다.'):
            limiter.authenticate('12345')
        self.assertEqual(limiter.used(), 2)


if __name__ == '__main__':
    unittest.main()
