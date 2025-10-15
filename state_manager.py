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

def ler_trades_ativos() -> list:
    """
    Lê a lista de símbolos de trades ativos do arquivo JSON.
    Retorna uma lista vazia se o arquivo não existir.
    """
    _garantir_diretorio()
    if not os.path.exists(STATE_FILE_PATH):
        return []

    try:
        with open(STATE_FILE_PATH, 'r') as f:
            trades = json.load(f)
            # Garante que sempre retornamos uma lista
            return trades if isinstance(trades, list) else []
    except (json.JSONDecodeError, IOError):
        # Se o arquivo estiver corrompido ou ilegível, retorna vazio
        return []

def escrever_trades_ativos(trades: list):
    """
    Escreve a lista de trades ativos no arquivo JSON.
    """
    _garantir_diretorio()
    with open(STATE_FILE_PATH, 'w') as f:
        json.dump(trades, f, indent=4)