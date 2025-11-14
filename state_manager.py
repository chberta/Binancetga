# -*- coding: utf-8 -*-

"""
Módulo Gerenciador de Estado

Responsável por ler e escrever o estado do robô, incluindo a lista de trades ativos
e a lista de ativos em período de "cooldown" (descanso).
"""

import os
import json
from logger_setup import logger
from datetime import datetime, timedelta
import config

# Define os caminhos para os arquivos de estado
TRADES_FILE_PATH = "data/trades_ativos.json"
COOLDOWN_FILE_PATH = "data/cooldown_assets.json"
HISTORICO_SYMBOLS_PATH = "data/historico_symbols.json"

def _garantir_diretorio():
    """Garante que o diretório 'data/' exista."""
    if not os.path.exists('data'):
        os.makedirs('data')

def ler_trades_ativos() -> list[dict]:
    """Lê a lista de dicionários de trades ativos do arquivo JSON."""
    _garantir_diretorio()
    if not os.path.exists(TRADES_FILE_PATH): return []
    try:
        with open(TRADES_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError): return []

def escrever_trades_ativos(trades: list[dict]):
    """Escreve a lista de dicionários de trades ativos no arquivo JSON."""
    _garantir_diretorio()
    with open(TRADES_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(trades, f, indent=4)

def adicionar_trade(novo_trade: dict):
    """Adiciona um novo trade à lista de trades ativos."""
    trades = ler_trades_ativos()
    if not any(t['symbol'] == novo_trade['symbol'] for t in trades):
        trades.append(novo_trade)
        escrever_trades_ativos(trades)
        logger.info(f"Trade para {novo_trade['symbol']} adicionado à memória.")

def remover_trade(symbol: str):
    """Remove um trade da lista de ativos e o adiciona à lista de cooldown."""
    trades = ler_trades_ativos()
    trades_filtrados = [t for t in trades if t.get('symbol') != symbol]
    if len(trades) > len(trades_filtrados):
        escrever_trades_ativos(trades_filtrados)
        logger.info(f"Trade para {symbol} removido da memória.")
        adicionar_ativo_cooldown(symbol)

# --- Funções de Cooldown ---

def ler_cooldown() -> dict:
    """Lê o dicionário de ativos em cooldown."""
    _garantir_diretorio()
    if not os.path.exists(COOLDOWN_FILE_PATH): return {}
    try:
        with open(COOLDOWN_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError): return {}

def escrever_cooldown(cooldown_data: dict):
    """Escreve o dicionário de ativos em cooldown."""
    _garantir_diretorio()
    with open(COOLDOWN_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cooldown_data, f, indent=4)

def adicionar_ativo_cooldown(symbol: str):
    """Adiciona um ativo à lista de cooldown com um timestamp de expiração."""
    cooldown_data = ler_cooldown()

    tf_map = {'h': 60, 'd': 1440, 'm': 1}
    timeframe_lower = config.TIMEFRAME.lower()
    multiplier = tf_map.get(timeframe_lower[-1], 1)
    tf_em_minutos = int(timeframe_lower[:-1]) * multiplier

    cooldown_em_minutos = tf_em_minutos * config.COOLDOWN_PERIODO_VELAS
    expiration_time = datetime.now() + timedelta(minutes=cooldown_em_minutos)

    cooldown_data[symbol] = expiration_time.isoformat()
    escrever_cooldown(cooldown_data)
    logger.info(f"Ativo {symbol} adicionado à lista de cooldown. Poderá ser negociado novamente após {expiration_time.strftime('%Y-%m-%d %H:%M')}.")

def obter_ativos_em_cooldown() -> list[str]:
    """Retorna uma lista de símbolos que ainda estão em cooldown."""
    cooldown_data = ler_cooldown()
    ativos_em_cooldown = []
    agora = datetime.now()

    for symbol, expiration_str in cooldown_data.items():
        if agora < datetime.fromisoformat(expiration_str):
            ativos_em_cooldown.append(symbol)

    # Limpa o arquivo de cooldown de entradas expiradas para mantê-lo organizado
    cooldown_limpo = {s: t for s, t in cooldown_data.items() if agora < datetime.fromisoformat(t)}
    if len(cooldown_limpo) != len(cooldown_data):
        escrever_cooldown(cooldown_limpo)

    return ativos_em_cooldown

# --- Funções de Histórico de Símbolos ---

def registrar_symbol_no_historico(symbol: str):
    """
    Registra um símbolo no arquivo de histórico de símbolos, se ainda não estiver presente.
    A lista é mantida em ordem alfabética.
    """
    _garantir_diretorio()

    # 1. Ler a lista existente
    historico = []
    if os.path.exists(HISTORICO_SYMBOLS_PATH):
        try:
            with open(HISTORICO_SYMBOLS_PATH, 'r', encoding='utf-8') as f:
                historico = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass # Se o arquivo estiver corrompido ou vazio, começamos do zero

    # 2. Adicionar o novo símbolo se ele não estiver na lista
    if symbol not in historico:
        historico.append(symbol)
        historico.sort() # Mantém a lista ordenada

        # 3. Escrever a lista atualizada de volta no arquivo
        with open(HISTORICO_SYMBOLS_PATH, 'w', encoding='utf-8') as f:
            json.dump(historico, f, indent=4)

        logger.info(f"Símbolo {symbol} adicionado ao histórico de símbolos operados.")
