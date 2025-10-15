# -*- coding: utf-8 -*-

"""
Módulo Gerenciador de Histórico

Responsável por registrar todas as operações concluídas em um arquivo
persistente (CSV), criando um "livro contábil" para análise de performance.
"""

import os
import csv
from datetime import datetime
from logger_setup import logger

HISTORY_FILE_PATH = "data/historico_trades.csv"
CSV_HEADER = [
    'timestamp_utc', 'symbol', 'entry_strategy', 'entry_price',
    'quantity', 'exit_price', 'pnl_usdt', 'pnl_percent'
]

def _garantir_arquivo_historico():
    """Garante que o diretório e o arquivo de histórico existam com o cabeçalho."""
    dir_name = os.path.dirname(HISTORY_FILE_PATH)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

    if not os.path.exists(HISTORY_FILE_PATH):
        with open(HISTORY_FILE_PATH, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)

def registrar_trade_concluido(trade_details: dict):
    """
    Registra os detalhes de um trade concluído no arquivo CSV.

    Espera um dicionário com chaves correspondentes ao CSV_HEADER,
    exceto 'timestamp_utc', que é adicionado automaticamente.
    """
    _garantir_arquivo_historico()

    try:
        with open(HISTORY_FILE_PATH, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADER)

            # Adiciona o timestamp atual e garante que todos os campos existam
            log_entry = {'timestamp_utc': datetime.utcnow().isoformat()}
            for header in CSV_HEADER[1:]: # Pula o timestamp que já adicionamos
                log_entry[header] = trade_details.get(header, 'N/A')

            writer.writerow(log_entry)
            logger.info(f"Histórico: Trade de {trade_details.get('symbol')} registrado com sucesso.")

    except (IOError, csv.Error) as e:
        logger.error(f"Erro ao registrar trade no histórico: {e}")