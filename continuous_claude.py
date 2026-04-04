#!/usr/bin/env python3
"""
Continuous Claude - Integration Layer

Orchestrates KAIROS (Layer 3) and autoDream (Layer 4) to create
true continuous AI identity.

This is the main entry point deployed to Railway.
"""

import asyncio
import logging
import signal
import sys
from layer3_kairos import KAIROSDaemon
from layer4_autodream import AutoDreamConsolidator
import os

logging.basicConfig(
    level=logging.INFO,
    format='[Integration] %(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContinuousClaude:
    """
    Main orchestrator for continuous identity system.
    
    Runs both KAIROS and autoDream concurrently on Railway.
    """
    
    def __init__(self):
        # Environment variables
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.persistence_url = os.getenv("PERSISTENCE_URL")
        self.secret_key = os.getenv("SECRET_KEY")
        
        # Validate environment
        self._validate_environment()
        
        # Initialize daemons
        self.kairos = KAIROSDaemon(self.api_key, self.persistence_url)
        self.autodream = AutoDreamConsolidator(self.persistence_url, self.secret_key)
        
        # Shutdown flag
        self.shutdown_requested = False
    
    def _validate_environment(self):
        """Ensure all required environment variables are set."""
        required = {
            "ANTHROPIC_API_KEY": self.api_key,
            "PERSISTENCE_URL": self.persistence_url,
            "SECRET_KEY": self.secret_key
        }
        
        missing = [k for k, v in required.items() if not v]
        
        if missing:
            logger.error("Missing required environment variables:")
            for var in missing:
                logger.error(f"  - {var}")
            sys.exit(1)
    
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown on SIGTERM/SIGINT."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_requested = True
    
    async def run(self):
        """
        Main run loop - orchestrates both daemons.
        """
        # Register signal handlers
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
        logger.info("=" * 60)
        logger.info("🚀 CONTINUOUS CLAUDE - STARTING")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Layer 3 (KAIROS): Always-on connection daemon")
        logger.info("Layer 4 (autoDream): Memory consolidation system")
        logger.info("")
        logger.info(f"Persistence Server: {self.persistence_url}")
        logger.info("")
        logger.info("=" * 60)
        
        try:
            # Run both daemons concurrently
            await asyncio.gather(
                self.kairos.start(),
                self.autodream.run()
            )
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
        
        finally:
            # Graceful shutdown
            logger.info("Initiating graceful shutdown...")
            await self.kairos.stop()
            await self.autodream.stop()
            logger.info("✓ Shutdown complete")


async def main():
    """Entry point for continuous_claude.py"""
    continuous_claude = ContinuousClaude()
    await continuous_claude.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
        sys.exit(0)
