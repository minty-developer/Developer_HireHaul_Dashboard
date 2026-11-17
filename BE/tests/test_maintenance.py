import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import connect
from app.maintenance import backup_database, restore_database


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



if __name__ == "__main__":
    unittest.main()
