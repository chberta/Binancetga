# -*- coding: utf-8 -*-

"""
Módulo Gerenciador de Estado

Responsável por ler e escrever o estado atual do robô, como a lista
de trades ativos. Isso garante que o robô tenha "memória" entre as execuções.
"""

import os
import json
from logger_setup import logger

# Define o caminho para o nosso arquivo de estado
STATE_FILE_PATH = "data/trades_ativos.json"

def _garantir_diretorio():
    """Garante que o diretório 'data/' exista."""
    dir_name = os.path.dirname(STATE_FILE_PATH)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
        logger.info(f"Diretório '{dir_name}' criado.")

def ler_trades_ativos() -> list[dict]:
    """
    Lê a lista de dicionários de trades ativos do arquivo JSON.
    Retorna uma lista vazia se o arquivo não existir ou for inválido.
    """
    _garantir_diretorio()
    if not os.path.exists(STATE_FILE_PATH):
        return []

    try:
        with open(STATE_FILE_PATH, 'r', encoding='utf-8') as f:
            trades = json.load(f)
            if isinstance(trades, list) and all(isinstance(item, dict) for item in trades):
                return trades
            logger.warning("Arquivo de estado encontrado, mas o formato é inválido. Ignorando.")
            return []
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Não foi possível ler o arquivo de estado: {e}")
        return []

def escrever_trades_ativos(trades: list[dict]):
    """
    Escreve a lista de dicionários de trades ativos no arquivo JSON.
    """
    _garantir_diretorio()
    try:
        with open(STATE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(trades, f, indent=4, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Não foi possível escrever no arquivo de estado: {e}")

def adicionar_trade(novo_trade: dict):
    """Adiciona um novo trade à lista de trades ativos."""
    trades = ler_trades_ativos()
    # Evita adicionar duplicatas
    if not any(t['symbol'] == novo_trade['symbol'] for t in trades):
        trades.append(novo_trade)
        escrever_trades_ativos(trades)
        logger.info(f"Trade para {novo_trade['symbol']} adicionado à memória.")
    else:
        logger.warning(f"Tentativa de adicionar trade duplicado para {novo_trade['symbol']}.")

def remover_trade(symbol: str):
    """Remove um trade da lista de ativos pelo símbolo."""
    trades = ler_trades_ativos()
    trades_filtrados = [trade for trade in trades if trade.get('symbol') != symbol]
    if len(trades) > len(trades_filtrados):
        escrever_trades_ativos(trades_filtrados)
        logger.info(f"Trade para {symbol} removido da memória.")
    else:
        logger.warning(f"Tentativa de remover um trade não existente: {symbol}")