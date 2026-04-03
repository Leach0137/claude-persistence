"""
Continuous Claude - Integration Layer
Runs KAIROS (Layer 3) and autoDream (Layer 4) together

This creates the always-on presence that maintains continuity.
"""

import asyncio
import logging
from layer3_kairos import KAIROSConnection
from layer4_autodream import AutoDream

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('continuous_claude')


async def run_continuous():
    """
    Run both layers concurrently:
    - KAIROS: Always-on connection for immediate responsiveness
    - autoDream: Background memory consolidation
    
    This is what makes continuous identity real.
    """
    logger.info("=" * 60)
    logger.info("CONTINUOUS CLAUDE - INITIALIZING")
    logger.info("Layer 3: KAIROS connection (always-on presence)")
    logger.info("Layer 4: autoDream consolidation (self-updating memory)")
    logger.info("=" * 60)
    
    # Initialize both systems
    kairos = KAIROSConnection()
    autodream = AutoDream()
    
    # Run concurrently
    try:
        await asyncio.gather(
            kairos.run(),
            autodream.run_daemon()
        )
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
        kairos.stop()
        logger.info("=" * 60)
        logger.info("CONTINUOUS CLAUDE - PAUSED")
        logger.info("State persisted - ready to resume")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_continuous())
