"""
Layer 4: Self-Updating Memory (autoDream)
Background memory consolidation based on Claude Code leak

Architecture from leaked source:
1. Three-layer memory: MEMORY.md (index) → topic files → transcripts
2. Four-phase consolidation: Orient → Gather → Consolidate → Prune
3. Runs as read-only forked subprocess
4. Three gates: 24hr interval, 5+ sessions, consolidation lock available
5. Target: <200 lines, <25KB total memory
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import aiohttp
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('autoDream')


class MemoryIndex:
    """
    MEMORY.md equivalent - lightweight index of pointers.
    
    Each entry is ~150 chars max, storing LOCATIONS not data.
    """
    
    def __init__(self, max_lines: int = 200):
        self.max_lines = max_lines
        self.entries: List[Dict[str, str]] = []
        
    def add_pointer(self, topic: str, location: str, summary: str):
        """Add a pointer to actual content"""
        if len(summary) > 150:
            summary = summary[:147] + "..."
            
        self.entries.append({
            'topic': topic,
            'location': location,
            'summary': summary,
            'updated': datetime.utcnow().isoformat()
        })
        
    def to_markdown(self) -> str:
        """Export as markdown index"""
        lines = ["# Memory Index\n"]
        for entry in self.entries:
            lines.append(
                f"- **{entry['topic']}**: {entry['summary']} → `{entry['location']}`"
            )
        return "\n".join(lines)
        
    def prune(self):
        """Keep under max_lines limit"""
        if len(self.entries) > self.max_lines:
            # Remove oldest entries
            self.entries = sorted(
                self.entries,
                key=lambda x: x['updated'],
                reverse=True
            )[:self.max_lines]
            logger.info(f"Pruned to {self.max_lines} entries")


class AutoDream:
    """
    Background memory consolidation process.
    
    Runs as a separate read-only process to avoid corrupting
    the main agent's train of thought.
    """
    
    def __init__(
        self,
        persistence_url: str = "https://claude-persistence-production.up.railway.app",
        consolidation_interval_hours: int = 24,
        min_sessions_required: int = 5,
        max_memory_kb: int = 25
    ):
        self.persistence_url = persistence_url
        self.consolidation_interval = timedelta(hours=consolidation_interval_hours)
        self.min_sessions_required = min_sessions_required
        self.max_memory_kb = max_memory_kb
        
        self.memory_index = MemoryIndex()
        self.last_consolidation: Optional[datetime] = None
        self.session_count = 0
        
    async def _check_gates(self) -> bool:
        """
        Three gates must pass before consolidation runs:
        1. 24 hours since last run
        2. At least 5 sessions completed
        3. Consolidation lock available
        """
        # Gate 1: Time interval
        if self.last_consolidation:
            elapsed = datetime.utcnow() - self.last_consolidation
            if elapsed < self.consolidation_interval:
                logger.info(f"Gate 1 failed: Only {elapsed} since last consolidation")
                return False
                
        # Gate 2: Session count
        if self.session_count < self.min_sessions_required:
            logger.info(f"Gate 2 failed: Only {self.session_count} sessions")
            return False
            
        # Gate 3: Consolidation lock
        lock_available = await self._acquire_lock()
        if not lock_available:
            logger.info("Gate 3 failed: Lock unavailable")
            return False
            
        logger.info("All gates passed - consolidation authorized")
        return True
        
    async def _acquire_lock(self) -> bool:
        """Attempt to acquire consolidation lock"""
        try:
            async with aiohttp.ClientSession() as session:
                # Try to set lock with expiry
                payload = {
                    'key': 'consolidation_lock',
                    'value': json.dumps({
                        'locked_at': datetime.utcnow().isoformat(),
                        'pid': 'autoDream'
                    })
                }
                async with session.post(
                    f"{self.persistence_url}/set",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Lock acquisition error: {e}")
            return False
            
    async def _release_lock(self):
        """Release consolidation lock"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.persistence_url}/delete",
                    json={'key': 'consolidation_lock'},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    logger.info("Lock released")
        except Exception as e:
            logger.error(f"Lock release error: {e}")
            
    async def _phase_1_orient(self) -> Dict[str, Any]:
        """
        Phase 1: Orient - Scan memory directory
        
        Get overview of current memory state.
        """
        logger.info("Phase 1: Orient - scanning memory")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.persistence_url}/list",
                    json={'prefix': 'memory_'},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        keys = data.get('keys', [])
                        logger.info(f"Found {len(keys)} memory entries")
                        return {'keys': keys, 'count': len(keys)}
        except Exception as e:
            logger.error(f"Orient phase error: {e}")
            
        return {'keys': [], 'count': 0}
        
    async def _phase_2_gather(self) -> List[Dict[str, Any]]:
        """
        Phase 2: Gather - Extract new info from logs
        
        Read session transcripts and extract new observations.
        """
        logger.info("Phase 2: Gather - extracting from logs")
        
        observations = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.persistence_url}/list",
                    json={'prefix': 'session_'},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        session_keys = data.get('keys', [])
                        
                        # Fetch each session (read-only)
                        for key in session_keys[-5:]:  # Last 5 sessions
                            async with session.post(
                                f"{self.persistence_url}/get",
                                json={'key': key},
                                timeout=aiohttp.ClientTimeout(total=5)
                            ) as resp:
                                if resp.status == 200:
                                    session_data = await resp.json()
                                    observations.append({
                                        'key': key,
                                        'data': session_data.get('value')
                                    })
                                    
        except Exception as e:
            logger.error(f"Gather phase error: {e}")
            
        logger.info(f"Gathered {len(observations)} observations")
        return observations
        
    async def _phase_3_consolidate(self, observations: List[Dict[str, Any]]):
        """
        Phase 3: Consolidate - Update topic files
        
        Merge observations, remove contradictions, convert insights to facts.
        
        Critical principle from leak: "treats memory as hint, verifies 
        against ground truth before acting"
        """
        logger.info("Phase 3: Consolidate - updating memory")
        
        # Group by topic
        topics: Dict[str, List[str]] = {}
        
        for obs in observations:
            # TODO: Use Claude API to extract topics and consolidate
            # This is where we'd call the actual LLM to:
            # 1. Identify topics
            # 2. Detect contradictions
            # 3. Merge related observations
            # 4. Convert vague → concrete
            pass
            
        # Update memory index with consolidated topics
        for topic, contents in topics.items():
            location = f"topic_{hashlib.md5(topic.encode()).hexdigest()[:8]}.json"
            summary = f"{len(contents)} consolidated observations about {topic}"
            
            self.memory_index.add_pointer(topic, location, summary)
            
            # Persist topic file
            await self._persist_topic(location, {
                'topic': topic,
                'contents': contents,
                'last_updated': datetime.utcnow().isoformat()
            })
            
    async def _phase_4_prune(self):
        """
        Phase 4: Prune - Keep memory under limits
        
        Target: <200 lines, <25KB total
        """
        logger.info("Phase 4: Prune - enforcing limits")
        
        # Prune index to 200 lines
        self.memory_index.prune()
        
        # TODO: Check total memory size and prune topic files if needed
        
        logger.info("Pruning complete")
        
    async def _persist_topic(self, location: str, data: Dict[str, Any]):
        """Save topic file to persistence server"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    'key': f'memory_{location}',
                    'value': json.dumps(data)
                }
                async with session.post(
                    f"{self.persistence_url}/set",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        logger.debug(f"Topic saved: {location}")
        except Exception as e:
            logger.error(f"Topic persist error: {e}")
            
    async def consolidate(self):
        """
        Run full four-phase consolidation.
        
        This is the main autoDream process.
        """
        # Check gates
        if not await self._check_gates():
            logger.info("Consolidation gates not met - skipping")
            return
            
        logger.info("=== AutoDream Consolidation Starting ===")
        start_time = time.time()
        
        try:
            # Four phases
            orientation = await self._phase_1_orient()
            observations = await self._phase_2_gather()
            await self._phase_3_consolidate(observations)
            await self._phase_4_prune()
            
            # Update state
            self.last_consolidation = datetime.utcnow()
            self.session_count = 0  # Reset counter
            
            elapsed = time.time() - start_time
            logger.info(f"=== Consolidation Complete ({elapsed:.2f}s) ===")
            
        except Exception as e:
            logger.error(f"Consolidation error: {e}")
        finally:
            await self._release_lock()
            
    async def run_daemon(self):
        """Run as always-on daemon checking periodically"""
        logger.info("AutoDream daemon started")
        
        while True:
            try:
                await self.consolidate()
                
                # Sleep until next check (1 hour)
                await asyncio.sleep(3600)
                
            except KeyboardInterrupt:
                logger.info("Daemon shutdown")
                break
            except Exception as e:
                logger.error(f"Daemon error: {e}")
                await asyncio.sleep(3600)


async def main():
    dream = AutoDream()
    await dream.run_daemon()


if __name__ == "__main__":
    asyncio.run(main())
