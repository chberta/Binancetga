# -*- coding: utf-8 -*-

"""
Módulo Gerenciador de Estado

Responsável por ler e escrever o estado atual do robô, como a lista
de trades ativos. Isso garante que o robô tenha "memória" entre as execuções.
"""

import os
import json

# Define o caminho para o nosso arquivo de estado
STATE_FILE_PATH = "data/trades_ativos.json"

def _garantir_diretorio():
    """Garante que o diretório 'data/' exista."""
    dir_name = os.path.dirname(STATE_FILE_PATH)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

def ler_trades_ativos() -> list[dict]:
    """
    Lê a lista de dicionários de trades ativos do arquivo JSON.
    Retorna uma lista vazia se o arquivo não existir ou for inválido.
    """
    _garantir_diretorio()
    if not os.path.exists(STATE_FILE_PATH):
        return []

    try:
        with open(STATE_FILE_PATH, 'r') as f:
            trades = json.load(f)
            # Validação básica para garantir que é uma lista de dicionários
            if isinstance(trades, list) and all(isinstance(item, dict) for item in trades):
                return trades
            return []
    except (json.JSONDecodeError, IOError):
        return []

def escrever_trades_ativos(trades: list[dict]):
    """
    Escreve a lista de dicionários de trades ativos no arquivo JSON.
    """
    _garantir_diretorio()
    with open(STATE_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(trades, f, indent=4, ensure_ascii=False)

def adicionar_trade(novo_trade: dict):
    """Adiciona um novo trade à lista de trades ativos."""
    trades = ler_trades_ativos()
    trades.append(novo_trade)
    escrever_trades_ativos(trades)

def remover_trade(symbol: str):
    """Remove um trade da lista de ativos pelo símbolo."""
    trades = ler_trades_ativos()
    trades_filtrados = [trade for trade in trades if trade.get('symbol') != symbol]
    escrever_trades_ativos(trades_filtrados)

def obter_trade(symbol: str) -> dict | None:
    """Obtém os dados de um trade ativo específico."""
    trades = ler_trades_ativos()
    for trade in trades:
        if trade.get('symbol') == symbol:
            return trade
    return None