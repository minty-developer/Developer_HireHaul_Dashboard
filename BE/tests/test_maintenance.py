import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import create_app
from app.db import connect
from app.maintenance import backup_database, restore_database, run_scheduler


class MaintenanceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp.name) / "test.db")
        self.backup_directory = str(Path(self.temp.name) / "backups")
        self.app = create_app({
            "TESTING": True,
            "APP_ENV": "testing",
            "DATABASE_PATH": self.database_path,
            "BACKUP_DIRECTORY": self.backup_directory,
            "ADMIN_API_KEY": "test-admin-key",
            "CORS_ORIGINS": "http://localhost:3000",
        })

    def tearDown(self):
        self.temp.cleanup()

    def test_backup_and_restore_database(self):
        with connect(self.database_path) as db:
            db.execute(
                "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
                ("backup@example.com", "hash", "Backup"),
            )
        backup = backup_database(self.database_path, self.backup_directory)
        with connect(self.database_path) as db:
            db.execute("DELETE FROM users")
        restore_database(self.database_path, str(backup))
        with connect(self.database_path) as db:
            count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(count, 1)

    @patch("app.maintenance.time.sleep", side_effect=StopIteration)
    def test_scheduler_collects_and_creates_backup(self, _sleep):
        collect = Mock(return_value={"failed": 0})
        report = Mock()
        with self.assertRaises(StopIteration):
            run_scheduler(
                collect,
                self.database_path,
                self.backup_directory,
                interval_seconds=60,
                timeout=5,
                retention_days=14,
                on_result=report,
            )
        collect.assert_called_once_with(self.database_path, timeout=5)
        report.assert_called_once_with({"failed": 0})
        self.assertEqual(len(list(Path(self.backup_directory).glob("*.db"))), 1)


if __name__ == "__main__":
    unittest.main()
