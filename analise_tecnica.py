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

def verificar_sinal_chilo_recente(client: Client, symbol: str) -> bool:
    """
    Verifica se a estratégia Chilo RSI emitiu um sinal de compra na vela mais recente.

    Args:
        client: O cliente da API da Binance.
        symbol: O símbolo do ativo a ser analisado.

    Returns:
        True se um sinal de compra ocorreu na última vela, False caso contrário.
    """
    try:
        # 1. Obter dados históricos (klines)
        klines = client.get_klines(symbol=symbol, interval=config.TIMEFRAME, limit=300)
        if len(klines) < config.CHILO_LENGTH + 1:
            return False

        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        # 2. Rodar a estratégia Chilo para obter a série de sinais de compra
        _, _, chilo_buy_signals = estrategia_chilo.getChiloStrategy(df)

        # 3. Verificar o sinal na última vela
        # .iloc[-2] porque a última vela (-1) é a vela atual que ainda não fechou.
        # Queremos o sinal na última vela fechada.
        if chilo_buy_signals is not None and not chilo_buy_signals.empty and len(chilo_buy_signals) > 1:
            if chilo_buy_signals.iloc[-2]:
                return True

    except Exception:
        # Em caso de qualquer erro, consideramos que não há sinal.
        return False

    return False
