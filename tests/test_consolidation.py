"""
Tests for ECHO-7 Consolidation Engine
Day 7: 7-Day Consolidation Tests
"""

import pytest
import os
import tempfile
import shutil
import json
from datetime import datetime, timedelta
from echo_core.memory.engine import MemoryEngine, MemoryType
from echo_core.memory.consolidation import ConsolidationEngine


class TestConsolidationEngine:

    def setup_method(self):
        """Create fresh memory engine and consolidation engine"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.memory = MemoryEngine(db_path=self.db_path)

        # Create a temporary archive directory
        self.archive_dir = tempfile.mkdtemp()
        self.consolidator = ConsolidationEngine(
            self.memory,
            archive_dir=self.archive_dir,
            days_threshold=1  # For testing, use 1 day
        )

    def teardown_method(self):
        """Clean up"""
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except:
            pass
        try:
            shutil.rmtree(self.archive_dir)
        except:
            pass

    def _insert_old_memory(self, content, days_old=2, importance=0.7, mem_type=MemoryType.RECENT):
        """Helper to insert a memory with a custom created_at date"""
        # We'll directly insert via SQL to set created_at in the past
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        created_at = (datetime.now() - timedelta(days=days_old)).isoformat()
        import uuid
        mem_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO memories
            (id, content, memory_type, importance_score, metadata, created_at, last_accessed, synced, consolidated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (mem_id, content, mem_type.value, importance, "{}", created_at, created_at, 0, 0))
        conn.commit()
        conn.close()
        return mem_id

    def test_consolidate_no_old_memories(self):
        """Test when no memories need consolidation"""
        self.memory.store("New memory", MemoryType.RECENT, 0.5)
        result = self.consolidator.consolidate()
        assert result["consolidated"] == 0
        assert "No memories to consolidate" in result["message"]

    def test_consolidate_with_old_memories(self):
        """Test consolidation with old memories"""
        # Insert an old memory (2 days old)
        self._insert_old_memory("Important project fact", days_old=2, importance=0.8)
        result = self.consolidator.consolidate()
        assert result["consolidated"] == 1
        assert result["important_archived"] == 1
        assert result["duplicates_removed"] == 0
        assert result["archive_file"] is not None
        assert "Topics" in result["summary"]

        # Verify the memory is now in archive tier
        archive_entries = self.memory.get_archive()
        assert len(archive_entries) == 1
        assert archive_entries[0].content == "Important project fact"

    def test_consolidate_duplicate_detection(self):
        """Test that duplicates are removed during consolidation"""
        # Insert two identical old memories
        self._insert_old_memory("Duplicate content", days_old=2, importance=0.7)
        self._insert_old_memory("Duplicate content", days_old=2, importance=0.7)
        result = self.consolidator.consolidate()
        assert result["consolidated"] == 2
        assert result["important_archived"] == 1
        assert result["duplicates_removed"] == 1

    def test_consolidate_low_importance_not_archived(self):
        """Test that low-importance memories are not archived in JSON"""
        self._insert_old_memory("Low importance note", days_old=2, importance=0.3)
        result = self.consolidator.consolidate()
        assert result["consolidated"] == 1
        assert result["important_archived"] == 0  # Not included in JSON

        # But it should still be in archive tier
        archive_entries = self.memory.get_archive()
        assert len(archive_entries) == 1
        assert archive_entries[0].content == "Low importance note"

    def test_search_archive(self):
        """Test searching archived memories"""
        self._insert_old_memory("Project X details", days_old=2, importance=0.8)
        self._insert_old_memory("Meeting notes", days_old=2, importance=0.7)
        self.consolidator.consolidate()

        results = self.consolidator.search_archive("Project")
        assert len(results) == 1
        assert "Project X" in results[0]["content"]

        results = self.consolidator.search_archive("Meeting")
        assert len(results) == 1

        results = self.consolidator.search_archive("nonexistent")
        assert len(results) == 0

    def test_consolidation_stats(self):
        """Test consolidation statistics"""
        self._insert_old_memory("Memory 1", days_old=2, importance=0.8)
        self._insert_old_memory("Memory 2", days_old=2, importance=0.6)
        self.consolidator.consolidate()

        stats = self.consolidator.get_consolidation_stats()
        assert stats["archive_entries"] == 2
        assert stats["avg_importance"] >= 0.6
        assert stats["consolidated_entries"] == 2
        assert stats["unconsolidated_entries"] == 0
        assert stats["total_archive_files"] == 1