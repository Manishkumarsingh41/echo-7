"""
ECHO-7 Memory Engine - 4-Tier Memory Hierarchy
Paper Section 3.2: Four-Tier Memory Hierarchy
"""

import sqlite3
import json
import uuid
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Optional

class MemoryType(Enum):
    WORKING = "working"
    RECENT = "recent"
    IMPORTANT = "important"
    ARCHIVE = "archive"

class MemoryEntry:
    def __init__(self, content: str, memory_type: MemoryType, 
                 importance_score: float = 0.0, metadata: dict = None):
        self.id = str(uuid.uuid4())
        self.content = content
        self.memory_type = memory_type
        self.importance_score = importance_score
        self.metadata = metadata or {}
        self.created_at = datetime.now().isoformat()
        self.last_accessed = datetime.now().isoformat()
        self.synced = False
        self.consolidated = False
        self.archive_path = None

class MemoryEngine:
    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        self._init_db()
        self.working_memory: List[MemoryEntry] = []
        self._load_working_memory()
    
    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                importance_score REAL DEFAULT 0.0,
                metadata TEXT,
                created_at TIMESTAMP,
                last_accessed TIMESTAMP,
                synced BOOLEAN DEFAULT 0,
                consolidated BOOLEAN DEFAULT 0,
                archive_path TEXT
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_synced ON memories(synced)")
        
        conn.commit()
        conn.close()
    
    def store(self, content: str, memory_type: MemoryType, 
              importance_score: float = 0.0) -> MemoryEntry:
        entry = MemoryEntry(content, memory_type, importance_score)
        
        if memory_type == MemoryType.WORKING:
            self.working_memory.append(entry)
            if len(self.working_memory) > 100:
                oldest = self.working_memory.pop(0)
                self._move_to_recent(oldest)
            return entry
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO memories 
            (id, content, memory_type, importance_score, metadata, 
             created_at, last_accessed, synced, consolidated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id, entry.content, entry.memory_type.value,
            entry.importance_score, json.dumps(entry.metadata),
            entry.created_at, entry.last_accessed,
            entry.synced, entry.consolidated
        ))
        
        conn.commit()
        conn.close()
        return entry
    
    def _move_to_recent(self, entry: MemoryEntry):
        entry.memory_type = MemoryType.RECENT
        entry.synced = False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO memories 
            (id, content, memory_type, importance_score, metadata,
             created_at, last_accessed, synced, consolidated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id, entry.content, entry.memory_type.value,
            entry.importance_score, json.dumps(entry.metadata),
            entry.created_at, entry.last_accessed,
            entry.synced, entry.consolidated
        ))
        
        conn.commit()
        conn.close()
    
    def get_recent(self, days: int = 7) -> List[MemoryEntry]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, content, memory_type, importance_score, metadata,
                   created_at, last_accessed, synced, consolidated
            FROM memories 
            WHERE memory_type = 'recent' 
            AND created_at > ?
            ORDER BY importance_score DESC
        """, (cutoff,))
        
        results = self._parse_results(cursor.fetchall())
        conn.close()
        return results
    
    def get_unsynced_recent(self) -> List[MemoryEntry]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, content, memory_type, importance_score, metadata,
                   created_at, last_accessed, synced, consolidated
            FROM memories 
            WHERE memory_type = 'recent' 
            AND synced = 0
            ORDER BY created_at ASC
        """)
        
        results = self._parse_results(cursor.fetchall())
        conn.close()
        return results
    
    def get_important(self) -> List[MemoryEntry]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, content, memory_type, importance_score, metadata,
                   created_at, last_accessed, synced, consolidated
            FROM memories 
            WHERE memory_type = 'important'
            ORDER BY importance_score DESC
        """)
        
        results = self._parse_results(cursor.fetchall())
        conn.close()
        return results
    
    def get_archive(self, query: Optional[str] = None) -> List[MemoryEntry]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if query:
            cursor.execute("""
                SELECT id, content, memory_type, importance_score, metadata,
                       created_at, last_accessed, synced, consolidated, archive_path
                FROM memories 
                WHERE memory_type = 'archive' 
                AND content LIKE ?
                ORDER BY created_at DESC
            """, (f"%{query}%",))
        else:
            cursor.execute("""
                SELECT id, content, memory_type, importance_score, metadata,
                       created_at, last_accessed, synced, consolidated, archive_path
                FROM memories 
                WHERE memory_type = 'archive'
                ORDER BY created_at DESC
                LIMIT 100
            """)
        
        results = self._parse_results(cursor.fetchall())
        conn.close()
        return results
    
    def _parse_results(self, rows) -> List[MemoryEntry]:
        results = []
        for row in rows:
            entry = MemoryEntry(
                content=row[1],
                memory_type=MemoryType(row[2]),
                importance_score=row[3]
            )
            entry.id = row[0]
            entry.metadata = json.loads(row[4]) if row[4] else {}
            entry.created_at = row[5]
            entry.last_accessed = row[6]
            entry.synced = bool(row[7])
            entry.consolidated = bool(row[8])
            if len(row) > 9:
                entry.archive_path = row[9]
            results.append(entry)
        return results
    
    def get_working_context(self, max_entries: int = 20) -> str:
        if not self.working_memory:
            return ""
        return "\n".join([m.content for m in self.working_memory[-max_entries:]])
    
    def clear_working(self):
        self.working_memory = []
    
    def _load_working_memory(self):
        pass
    
    def get_stats(self) -> Dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        for mem_type in ['recent', 'important', 'archive']:
            cursor.execute(
                "SELECT COUNT(*) FROM memories WHERE memory_type = ?",
                (mem_type,)
            )
            stats[mem_type] = cursor.fetchone()[0]
        
        stats['working'] = len(self.working_memory)
        conn.close()
        return stats