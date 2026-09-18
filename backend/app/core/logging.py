import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        stream=sys.stdout,
        force=True,
    )
    # 压掉三方库噪音
    for noisy in ("httpx", "httpcore", "minio", "asyncio", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
