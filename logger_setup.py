# -*- coding: utf-8 -*-

"""
Módulo de Configuração do Logger

Configura um logger padrão para o projeto, com saída para o console
e para um arquivo de log persistente.
"""

import logging
import sys
import config

def setup_logger():
    """
    Configura e retorna um logger.
    """
    # Define o formato da mensagem de log
    log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    # Cria o logger principal
    logger = logging.getLogger('robot_trader')
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    # Evita adicionar múltiplos handlers se a função for chamada mais de uma vez
    if logger.hasHandlers():
        logger.handlers.clear()

    # Handler para o console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # Handler para o arquivo
    try:
        file_handler = logging.FileHandler(config.LOG_FILE, mode='a', encoding='utf-8')
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Não foi possível configurar o log em arquivo: {e}")

    return logger

# Cria uma instância global do logger para ser importada por outros módulos
logger = setup_logger()