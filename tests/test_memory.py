"""
Tests for ECHO-7 Memory Engine
Day 3: Memory Engine Tests
"""

import pytest
import os
import tempfile
import time
from echo_core.memory.engine import MemoryEngine, MemoryType

class TestMemoryEngine:
    
    def setup_method(self):
        """Create a fresh memory engine for each test"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()  # Close so SQLite can use it
        self.engine = MemoryEngine(db_path=self.db_path)
    
    def teardown_method(self):
        """Clean up temp file"""
        # Force close any SQLite connections
        if hasattr(self, 'engine'):
            try:
                import sqlite3
                conn = sqlite3.connect(self.db_path)
                conn.close()
            except:
                pass
        
        # Wait a moment for Windows to release file
        time.sleep(0.1)
        
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except PermissionError:
            # File might still be locked, try one more time
            time.sleep(0.2)
            try:
                if os.path.exists(self.db_path):
                    os.unlink(self.db_path)
            except:
                pass
    
    def test_store_working(self):
        """Test storing in working memory"""
        entry = self.engine.store("Test message", MemoryType.WORKING, 0.5)
        assert entry.content == "Test message"
        assert entry.memory_type == MemoryType.WORKING
        assert len(self.engine.working_memory) == 1
    
    def test_store_recent(self):
        """Test storing in recent memory"""
        entry = self.engine.store("Test message", MemoryType.RECENT, 0.7)
        assert entry.content == "Test message"
        assert entry.memory_type == MemoryType.RECENT
        
        recent = self.engine.get_recent()
        assert len(recent) == 1
        assert recent[0].content == "Test message"
    
    def test_store_important(self):
        """Test storing in important memory"""
        entry = self.engine.store("Important fact", MemoryType.IMPORTANT, 0.9)
        assert entry.content == "Important fact"
        
        important = self.engine.get_important()
        assert len(important) == 1
        assert important[0].content == "Important fact"
    
    def test_working_memory_bounded(self):
        """Test working memory doesn't grow indefinitely"""
        for i in range(150):
            self.engine.store(f"Message {i}", MemoryType.WORKING, 0.0)
        
        assert len(self.engine.working_memory) <= 100
    
    def test_get_working_context(self):
        """Test building context from working memory"""
        for i in range(5):
            self.engine.store(f"Message {i}", MemoryType.WORKING, 0.0)
        
        context = self.engine.get_working_context()
        assert "Message 0" in context
        assert "Message 4" in context
    
    def test_get_stats(self):
        """Test statistics gathering"""
        self.engine.store("Test 1", MemoryType.WORKING, 0.0)
        self.engine.store("Test 2", MemoryType.RECENT, 0.7)
        self.engine.store("Test 3", MemoryType.IMPORTANT, 0.9)
        
        stats = self.engine.get_stats()
        assert stats['working'] == 1
        assert stats['recent'] == 1
        assert stats['important'] == 1
    
    def test_working_to_recent_migration(self):
        """Test working memory moves to recent when full"""
        for i in range(110):
            self.engine.store(f"Message {i}", MemoryType.WORKING, 0.0)
        
        stats = self.engine.get_stats()
        assert stats['working'] == 100
        assert stats['recent'] >= 10
    
    def test_get_unsynced_recent(self):
        """Test getting unsynced recent memories"""
        self.engine.store("Test unsynced", MemoryType.RECENT, 0.7)
        
        unsynced = self.engine.get_unsynced_recent()
        assert len(unsynced) == 1
        assert unsynced[0].content == "Test unsynced"
        assert unsynced[0].synced == False
    
    def test_archive_storage(self):
        """Test archive tier storage"""
        entry = self.engine.store("Archived memory", MemoryType.ARCHIVE, 0.5)
        assert entry.memory_type == MemoryType.ARCHIVE
        
        archive = self.engine.get_archive()
        assert len(archive) >= 1
    
    def test_archive_search(self):
        """Test archive search functionality"""
        self.engine.store("Project ECHO-7", MemoryType.ARCHIVE, 0.8)
        self.engine.store("Other project", MemoryType.ARCHIVE, 0.6)
        
        results = self.engine.get_archive(query="ECHO")
        assert len(results) >= 1
        assert "ECHO-7" in results[0].content