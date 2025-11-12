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

        # A vela que nos interessa é a última fechada (penúltima da lista)
        ultima_vela_fechada_idx = -2

        # Se a última vela fechada não está em estado de compra, não há sinal ativo.
        if not chilo_state_signals.iloc[ultima_vela_fechada_idx]:
            return SEM_SINAL, 0

        # --- Lógica de Cruzamento: Identificar a "vela de ignição" do sinal ---
        # Um cruzamento ocorre onde o sinal era Falso e na vela seguinte se torna Verdadeiro.
        sinal_anterior = chilo_state_signals.shift(1)
        cruzamento_para_compra = (chilo_state_signals == True) & (sinal_anterior == False)

        # Encontra os índices onde ocorreram os cruzamentos
        indices_cruzamento = cruzamento_para_compra[cruzamento_para_compra].index

        # Se não houve nenhum cruzamento (ex: a série já começa com True), não consideramos um sinal válido.
        if indices_cruzamento.empty:
            return SEM_SINAL, 0

        # Pega o índice do cruzamento mais recente
        ultimo_cruzamento_idx = indices_cruzamento[-1]

        # Calcula a idade do sinal
        # A idade é a distância entre a vela atual (última fechada) e a vela onde o sinal começou.
        # Idade 0 = sinal na última vela fechada. Idade 1 = sinal na penúltima, e assim por diante.
        indice_df_ultima_vela = len(chilo_state_signals) + ultima_vela_fechada_idx
        idade_sinal = indice_df_ultima_vela - ultimo_cruzamento_idx

        return SINAL_COMPRA, idade_sinal

    except Exception:
        return SEM_SINAL, 0
