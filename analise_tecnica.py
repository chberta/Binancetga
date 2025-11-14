# -*- coding: utf-8 -*-

"""
Módulo de Análise Técnica
"""

import config
import pandas as pd
import ta
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

        buy_cross, sell_cross, buy_state = estrategia_chilo.getChiloStrategy(df)

        if buy_cross is None or sell_cross is None or len(buy_cross) < 2:
            return SEM_SINAL, 0

        # --- Lógica de Dupla Verificação ---
        # 1. Encontrar os índices dos últimos sinais de compra e venda
        indices_compra = buy_cross[buy_cross].index
        indices_venda = sell_cross[sell_cross].index

        # Se não houver nenhum sinal de compra, não há oportunidade
        if indices_compra.empty:
            return SEM_SINAL, 0

        ultimo_sinal_compra_idx = indices_compra[-1]

        # 2. Verificar se há um sinal de venda que invalida o sinal de compra
        if not indices_venda.empty:
            ultimo_sinal_venda_idx = indices_venda[-1]
            # Se o último sinal de venda for mais recente que o último de compra, a oportunidade é inválida
            if ultimo_sinal_venda_idx > ultimo_sinal_compra_idx:
                return SEM_SINAL, 0

        # 3. Se a verificação do Chilo passar, adicionar o filtro de RSI como confirmação
        rsi = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        ultima_vela_fechada_idx = -2

        # Se o RSI da última vela fechada for > 50, o sinal é forte.
        if rsi.iloc[ultima_vela_fechada_idx] > 50:
            # A idade é a distância da última vela fechada para a vela do sinal de compra
            idade_sinal = (len(df) - 2) - ultimo_sinal_compra_idx
            return SINAL_COMPRA, idade_sinal

        # Se o RSI for menor ou igual a 50, o sinal é fraco e será ignorado.
        return SEM_SINAL, 0

    except Exception:
        return SEM_SINAL, 0
