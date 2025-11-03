# -*- coding: utf-8 -*-

"""
Módulo de Análise Técnica
"""

import config
import pandas as pd
import estrategia_chilo
from binance.client import Client

# Definição dos possíveis status do sinal
SINAL_COMPRA = "SINAL_COMPRA"
SEM_SINAL = "SEM_SINAL"

def get_chilo_signal_status(client: Client, symbol: str) -> tuple[str, int]:
    """
    Verifica o status do sinal Chilo RSI para um ativo.

    Retorna uma tupla com:
    - O status do sinal ('SINAL_COMPRA' ou 'SEM_SINAL').
    - A idade do sinal em velas (0 se não houver sinal).
    """
    try:
        klines = client.get_klines(symbol=symbol, interval=config.TIMEFRAME, limit=300)
        if len(klines) < config.CHILO_LENGTH + 5:
            return SEM_SINAL, 0

        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        chilo_cross_signals, chilo_state_signals = estrategia_chilo.getChiloStrategy(df)

        if chilo_state_signals is None or chilo_state_signals.empty or len(chilo_state_signals) < 2:
            return SEM_SINAL, 0

        # Analisa a última vela fechada (índice -2)
        ultima_vela_idx = -2

        # Se a última vela fechada não está em estado de compra, não há sinal.
        if not chilo_state_signals.iloc[ultima_vela_idx]:
            return SEM_SINAL, 0

        # Se está em estado de compra, calcula há quantas velas começou.
        idade_sinal = 0
        # Itera de trás para frente a partir da última vela fechada
        for i in range(len(chilo_state_signals) + ultima_vela_idx, -1, -1):
            if chilo_state_signals.iloc[i]:
                # Se o sinal de cruzamento aconteceu neste candle, a idade é a contagem.
                if chilo_cross_signals.iloc[i]:
                    idade_sinal += 1
                    break
                else:
                    idade_sinal += 1
            else:
                # Chegou ao fim da tendência de compra
                break

        return SINAL_COMPRA, idade_sinal

    except Exception:
        return SEM_SINAL, 0
