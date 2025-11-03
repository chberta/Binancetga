# -*- coding: utf-8 -*-

"""
Módulo de Análise Técnica

Este módulo contém a lógica para analisar um ativo e identificar
sinais de compra com base na estratégia definida.
"""

import config
import pandas as pd
import estrategia_chilo
from binance.client import Client

# Definição dos possíveis status do sinal para clareza
SINAL_RECENTE = "SINAL_RECENTE"
SINAL_ANTIGO = "SINAL_ANTIGO"
SEM_SINAL = "SEM_SINAL"

def get_chilo_signal_status(client: Client, symbol: str) -> str:
    """
    Verifica o status do sinal Chilo RSI para um ativo.

    Retorna um de três estados:
    - SINAL_RECENTE: Se o cruzamento de compra ocorreu na última vela fechada.
    - SINAL_ANTIGO: Se o ativo está em tendência de compra, mas o cruzamento não foi recente.
    - SEM_SINAL: Se não há tendência de compra.
    """
    try:
        # 1. Obter dados históricos
        klines = client.get_klines(symbol=symbol, interval=config.TIMEFRAME, limit=300)
        if len(klines) < config.CHILO_LENGTH + 5: # Buffer de segurança
            return SEM_SINAL

        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        # 2. Rodar a estratégia para obter os sinais
        chilo_cross_signals, chilo_state_signals = estrategia_chilo.getChiloStrategy(df)

        if chilo_cross_signals is None or chilo_state_signals is None or len(chilo_cross_signals) < 2:
            return SEM_SINAL

        # 3. Analisar a última vela fechada (índice -2)
        ultima_vela_fechada_idx = -2

        # Verifica se o cruzamento de compra ocorreu na última vela fechada
        if chilo_cross_signals.iloc[ultima_vela_fechada_idx]:
            return SINAL_RECENTE

        # Se não houve cruzamento recente, verifica se a tendência de compra já está ativa
        if chilo_state_signals.iloc[ultima_vela_fechada_idx]:
            return SINAL_ANTIGO

    except Exception:
        return SEM_SINAL

    return SEM_SINAL
