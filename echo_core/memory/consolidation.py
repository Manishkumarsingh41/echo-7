"""
ECHO-7 Consolidation Engine
Paper Section 3.5: 7-Day Consolidation

Automatically consolidates memories older than 7 days:
- Deduplication
- Extract important information (importance > 0.6)
- Generate a summary
- Store permanently in archive as JSON
- Update database to archive tier
"""

import json
import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from echo_core.memory.engine import MemoryEngine, MemoryType, MemoryEntry


class ConsolidationEngine:
    """
    7-day memory consolidation with deduplication and archiving.
    """

    def __init__(
        self,
        memory_engine: MemoryEngine,
        archive_dir: str = "data/archives/",
        days_threshold: int = 7
    ):
        self.memory = memory_engine
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.days_threshold = days_threshold
        self._logger = None  # optional

    def consolidate(self) -> Dict[str, Any]:
        """
        Run consolidation: find recent memories older than threshold,
        deduplicate, extract important, create archive, and update DB.
        Returns a report.
        """
        cutoff = datetime.now() - timedelta(days=self.days_threshold)
        cutoff_iso = cutoff.isoformat()

        conn = sqlite3.connect(self.memory.db_path)
        cursor = conn.cursor()

        # 1. Fetch unsynced, non-consolidated recent memories older than threshold
        cursor.execute("""
            SELECT id, content, memory_type, importance_score, metadata,
                   created_at, last_accessed, synced, consolidated
            FROM memories
            WHERE memory_type = 'recent'
            AND consolidated = 0
            AND created_at < ?
            ORDER BY importance_score DESC
        """, (cutoff_iso,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {
                "consolidated": 0,
                "message": "No memories to consolidate at this time.",
                "archive_file": None
            }

        # 2. Deduplicate: group by content hash
        seen_hashes = set()
        important_memories = []  # will store dicts
        duplicates_removed = 0
        total_processed = 0

        for row in rows:
            total_processed += 1
            content = row[1]
            content_hash = hashlib.md5(content.encode()).hexdigest()
            if content_hash in seen_hashes:
                duplicates_removed += 1
                continue
            seen_hashes.add(content_hash)

            # keep if importance >= 0.6 (high)
            if row[3] >= 0.6:
                important_memories.append({
                    "id": row[0],
                    "content": row[1],
                    "importance": row[3],
                    "metadata": json.loads(row[4]) if row[4] else {},
                    "created_at": row[5],
                    "last_accessed": row[6],
                    "synced": bool(row[7]),
                    "consolidated": bool(row[8])
                })

        # 3. Generate archive file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_filename = f"archive_{timestamp}.json"
        archive_path = self.archive_dir / archive_filename

        # 4. Write archive
        archive_data = {
            "timestamp": datetime.now().isoformat(),
            "count": len(important_memories),
            "entries": important_memories,
            "summary": self._generate_summary(important_memories)
        }

        with open(archive_path, 'w', encoding='utf-8') as f:
            json.dump(archive_data, f, indent=2, ensure_ascii=False)

        # 5. Update database: mark as archive, set archive_path, consolidated=1
        conn = sqlite3.connect(self.memory.db_path)
        cursor = conn.cursor()

        # Update important memories to archive
        for entry in important_memories:
            cursor.execute("""
                UPDATE memories
                SET memory_type = 'archive',
                    consolidated = 1,
                    archive_path = ?
                WHERE id = ?
            """, (str(archive_path), entry["id"]))

        # Move all other processed rows to archive as well (even low importance)
        for row in rows:
            # Check if already updated (skip if in important_memories)
            # We'll update all rows from the original set
            cursor.execute("""
                UPDATE memories
                SET memory_type = 'archive',
                    consolidated = 1,
                    archive_path = ?
                WHERE id = ?
            """, (str(archive_path), row[0]))

        conn.commit()
        conn.close()

        return {
            "consolidated": total_processed,
            "important_archived": len(important_memories),
            "duplicates_removed": duplicates_removed,
            "archive_file": str(archive_path),
            "summary": archive_data["summary"]
        }

    def _generate_summary(self, memories: List[Dict]) -> str:
        """Generate a text summary of consolidated memories."""
        if not memories:
            return "No important memories in this period."

        # Extract topics (simple heuristic)
        word_freq = {}
        for mem in memories:
            content = mem["content"]
            for word in content.split():
                if len(word) > 4:
                    word_freq[word] = word_freq.get(word, 0) + 1

        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        top_words_str = ", ".join([w[0] for w in top_words])

        return f"Consolidated {len(memories)} important memories. Topics: {top_words_str}"

    def search_archive(self, query: str) -> List[Dict]:
        """
        Search archived memories by query (text search).
        """
        results = []
        for archive_file in self.archive_dir.glob("*.json"):
            with open(archive_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for entry in data.get("entries", []):
                    if query.lower() in entry["content"].lower():
                        results.append({
                            "archive_file": str(archive_file),
                            "content": entry["content"],
                            "importance": entry["importance"],
                            "created_at": entry.get("created_at", "")
                        })
        return results

    def get_consolidation_stats(self) -> Dict:
        """
        Get statistics about the archive and consolidation.
        Fixed: count consolidated entries across all memory types.
        """
        conn = sqlite3.connect(self.memory.db_path)
        cursor = conn.cursor()

        # Number of archive entries
        cursor.execute("""
            SELECT COUNT(*), AVG(importance_score)
            FROM memories
            WHERE memory_type = 'archive'
        """)
        archive_count, avg_importance = cursor.fetchone()

        # Total consolidated entries (regardless of type)
        cursor.execute("""
            SELECT COUNT(*)
            FROM memories
            WHERE consolidated = 1
        """)
        consolidated_count = cursor.fetchone()[0]

        # Unconsolidated recent entries
        cursor.execute("""
            SELECT COUNT(*)
            FROM memories
            WHERE memory_type = 'recent'
            AND consolidated = 0
        """)
        unconsolidated_count = cursor.fetchone()[0]

        conn.close()

        total_archive_files = len(list(self.archive_dir.glob("*.json")))

        return {
            "archive_entries": archive_count or 0,
            "avg_importance": avg_importance or 0.0,
            "consolidated_entries": consolidated_count or 0,
            "unconsolidated_entries": unconsolidated_count or 0,
            "total_archive_files": total_archive_files
        }