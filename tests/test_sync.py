"""
Tests for ECHO-7 Delta Sync Engine
Day 6: Encrypted Delta Sync Tests
"""

import pytest
import os
import tempfile
import shutil
from echo_core.memory.engine import MemoryEngine, MemoryType
from echo_core.memory.sync import DeltaSyncEngine
from echo_core.crypto.key_manager import StableKeyManager


class TestDeltaSyncEngine:

    def setup_method(self):
        """Create fresh memory engine and sync engine"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.memory = MemoryEngine(db_path=self.db_path)
        self.sync = DeltaSyncEngine(self.memory, user_id="test_user")

        # Use a test-specific key file
        self.key_file = "data/keys/test_key.key"
        self.key_mgr = StableKeyManager(key_file=self.key_file)
        if self.key_mgr.has_key():
            self.key_mgr.delete_key()

        self.password = "test_password_123"

    def teardown_method(self):
        """Clean up temp files and test key"""
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except:
            pass

        # Delete test key
        try:
            if os.path.exists(self.key_file):
                os.unlink(self.key_file)
        except:
            pass

    def _create_second_db(self):
        """Create a separate database for Device B"""
        temp_db2 = tempfile.NamedTemporaryFile(delete=False)
        db2_path = temp_db2.name
        temp_db2.close()
        return db2_path

    def test_generate_delta_no_unsynced(self):
        """Test delta generation when no unsynced memories exist"""
        result = self.sync.generate_delta()
        assert result["has_delta"] is False
        assert result["entry_count"] == 0

    def test_generate_delta_with_unsynced(self):
        """Test delta generation with unsynced memories"""
        self.memory.store("Test sync memory", MemoryType.RECENT, 0.7)
        result = self.sync.generate_delta()
        assert result["has_delta"] is True
        assert result["entry_count"] == 1
        assert "encrypted_data" in result

    def test_generate_delta_with_password(self):
        """Test delta generation with password-based key"""
        self.memory.store("Test with password", MemoryType.RECENT, 0.8)
        result = self.sync.generate_delta(password=self.password)
        assert result["has_delta"] is True
        assert result["entry_count"] == 1

    def test_merge_delta(self):
        """Test merging delta from another device with separate databases"""
        # Device A: store and generate delta
        self.memory.store("Device A memory", MemoryType.RECENT, 0.7)
        delta = self.sync.generate_delta()

        # Device B: create NEW database (separate file)
        db2_path = self._create_second_db()
        memory_b = MemoryEngine(db_path=db2_path)
        sync_b = DeltaSyncEngine(memory_b, user_id="test_user")

        # Merge delta
        merged_count = sync_b.merge_delta(delta["encrypted_data"])
        assert merged_count == 1

        # Verify memory was merged into Device B
        recent_b = memory_b.get_recent()
        assert len(recent_b) == 1
        assert recent_b[0].content == "Device A memory"

        # Cleanup
        try:
            os.unlink(db2_path)
        except:
            pass

    def test_merge_delta_with_password(self):
        """Test merging delta with password and separate databases"""
        # Device A: store and generate delta with password
        self.memory.store("Device A password memory", MemoryType.RECENT, 0.7)
        delta = self.sync.generate_delta(password=self.password)

        # Device B: new database
        db2_path = self._create_second_db()
        memory_b = MemoryEngine(db_path=db2_path)
        sync_b = DeltaSyncEngine(memory_b, user_id="test_user")

        # Merge with password
        merged_count = sync_b.merge_delta(delta["encrypted_data"], password=self.password)
        assert merged_count == 1

        recent_b = memory_b.get_recent()
        assert len(recent_b) == 1
        assert recent_b[0].content == "Device A password memory"

        try:
            os.unlink(db2_path)
        except:
            pass

    def test_merge_delta_duplicate_handling(self):
        """Test that duplicate entries are not merged"""
        # Device A: store and generate delta
        self.memory.store("Original memory", MemoryType.RECENT, 0.7)
        delta1 = self.sync.generate_delta()

        # Device B: new database
        db2_path = self._create_second_db()
        memory_b = MemoryEngine(db_path=db2_path)
        sync_b = DeltaSyncEngine(memory_b, user_id="test_user")

        # Merge first time
        count1 = sync_b.merge_delta(delta1["encrypted_data"])
        assert count1 == 1

        # Try to merge same delta again
        count2 = sync_b.merge_delta(delta1["encrypted_data"])
        assert count2 == 0  # No new entries

        # Verify only one entry exists
        recent = memory_b.get_recent()
        assert len(recent) == 1

        try:
            os.unlink(db2_path)
        except:
            pass

    def test_sync_stats(self):
        """Test sync statistics collection"""
        self.memory.store("Memory 1", MemoryType.RECENT, 0.7)
        self.memory.store("Memory 2", MemoryType.RECENT, 0.8)
        self.sync.generate_delta()  # Sync all

        stats = self.sync.get_sync_stats()
        assert stats["total_entries"] == 2
        assert stats["synced_entries"] == 2
        assert stats["unsynced_entries"] == 0

    def test_user_id_mismatch(self):
        """Test that user_id mismatch prevents merge"""
        self.memory.store("Test memory", MemoryType.RECENT, 0.7)

        # Device A: generate delta with user_id "device_a"
        sync_a = DeltaSyncEngine(self.memory, user_id="device_a")
        delta = sync_a.generate_delta()

        # Device B: different user_id
        db2_path = self._create_second_db()
        memory_b = MemoryEngine(db_path=db2_path)
        sync_b = DeltaSyncEngine(memory_b, user_id="device_b")

        merged_count = sync_b.merge_delta(delta["encrypted_data"])
        assert merged_count == 0  # Should reject due to user mismatch

        try:
            os.unlink(db2_path)
        except:
            pass

    def test_clear_sync_status(self):
        """Test clearing sync flags"""
        self.memory.store("Test memory", MemoryType.RECENT, 0.7)
        self.sync.generate_delta()

        stats = self.sync.get_sync_stats()
        assert stats["synced_entries"] == 1

        self.sync.clear_sync_status()
        stats = self.sync.get_sync_stats()
        assert stats["synced_entries"] == 0
        assert stats["unsynced_entries"] == 1