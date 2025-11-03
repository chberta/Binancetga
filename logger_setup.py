# -*- coding: utf-8 -*-

"""
Módulo de Configuração do Logger

Configura dois loggers:
1. Um logger principal para o log geral de atividades.
2. Um logger dedicado para registrar apenas operações de trade (compras/vendas).
"""

import logging
import sys
import config
import os

def setup_loggers():
    """Configura e retorna os dois loggers: principal e de trades."""
    # Garante que o diretório de logs exista
    log_dir = os.path.dirname(config.LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # --- Configuração do Logger Principal ---
    log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    logger = logging.getLogger('robot_trader')
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    if not logger.handlers:
        # Handler para o console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)
        # Handler para o arquivo principal
        try:
            file_handler = logging.FileHandler(config.LOG_FILE, mode='a', encoding='utf-8')
            file_handler.setFormatter(log_format)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"Não foi possível configurar o log em arquivo principal: {e}")

    # --- Configuração do Logger de Trades ---
    trade_log_format = logging.Formatter('%(asctime)s,%(message)s')
    trades_logger = logging.getLogger('trades_logger')
    trades_logger.setLevel(logging.INFO) # O log de trades sempre registrará as informações
    trades_logger.propagate = False # Evita que o log de trades vá para o logger principal
    if not trades_logger.handlers:
        try:
            trade_file_handler = logging.FileHandler(config.TRADES_LOG_FILE, mode='a', encoding='utf-8')
            trade_file_handler.setFormatter(trade_log_format)
            trades_logger.addHandler(trade_file_handler)
        except Exception as e:
            logger.error(f"Não foi possível configurar o log de trades: {e}")

    return logger, trades_logger

# Cria instâncias globais para serem importadas
logger, trades_logger = setup_loggers()
