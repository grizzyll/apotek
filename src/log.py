import logging
import os
import sys

def setup_logger(name="apotek", log_level="INFO"):
    """
    Menyiapkan logger terstandar untuk aplikasi (Action 2, 10, 14).
    Format log konsisten: Waktu | Level | Modul | Pesan
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s.%(module)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger
