# -*- coding: utf-8 -*-

import config
import pandas as pd
import numpy as np
import ta
from ta.utils import dropna

def calcular_ut_bot(high, low, close, periodo=config.UT_BOT_PERIODO, multiplicador=config.UT_BOT_ATR_MULTIPLICADOR):
    """
    Calcula o indicador UT Bot Alerts de forma robusta e corrigida.
    """
    atr = ta.volatility.average_true_range(high, low, close, window=periodo)
    ema = ta.trend.ema_indicator(close, window=periodo)

    # Encontra o primeiro índice onde tanto a ema quanto o atr são válidos
    first_valid_index = ema.first_valid_index()
    if first_valid_index is None or atr.first_valid_index() is None:
        # Retorna séries vazias se não houver dados suficientes
        return pd.Series(index=close.index, dtype=float), pd.Series(index=close.index, dtype=float)

    start_index = max(first_valid_index, atr.first_valid_index())

    trailing_stop = pd.Series(np.nan, index=close.index)
    sinal = pd.Series(np.nan, index=close.index)

    # Inicializa o primeiro valor válido
    sinal.loc[start_index] = 1.0
    trailing_stop.loc[start_index] = ema.loc[start_index] - multiplicador * atr.loc[start_index]

    for i in range(close.index.get_loc(start_index) + 1, len(close)):
        prev_sinal = sinal.iloc[i-1]
        prev_stop = trailing_stop.iloc[i-1]

        if close.iloc[i] > prev_stop:
            sinal.iloc[i] = 1.0
            trailing_stop.iloc[i] = max(prev_stop, ema.iloc[i] - multiplicador * atr.iloc[i])
        else:
            sinal.iloc[i] = -1.0
            trailing_stop.iloc[i] = min(prev_stop, ema.iloc[i] + multiplicador * atr.iloc[i])

    return trailing_stop, sinal

import estrategia_chilo

def calcular_score_ativo(client, symbol):
    """
    Calcula o score de um único ativo e retorna detalhes dos indicadores.
    Retorna: score (int), df (DataFrame), detalhes (dict)
    """
    try:
        # 1. Obter dados históricos (klines)
        # Aumentar o limite para garantir dados suficientes para Chilo
        klines = client.get_klines(symbol=symbol, interval=config.TIMEFRAME, limit=300)
        if not klines:
            return 0, None, {}

        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        # 2. Calcular Indicadores
        df['ma_curta'] = ta.trend.sma_indicator(df['close'], window=config.MA_CURTA)
        df['ma_longa'] = ta.trend.sma_indicator(df['close'], window=config.MA_LONGA)
        df['rsi'] = ta.momentum.rsi(df['close'], window=config.RSI_PERIODO)
        df['ut_stop'], df['ut_sinal'] = calcular_ut_bot(df['high'], df['low'], df['close'])

        df.dropna(inplace=True)
        if df.empty:
            return 0, None, {}

        # 4. Lógica de Score
        score = 0
        ultimo_registro = df.iloc[-1]
        penultimo_registro = df.iloc[-2]

        if ultimo_registro['ma_curta'] > ultimo_registro['ma_longa']:
            score += 1
            if penultimo_registro['ma_curta'] <= penultimo_registro['ma_longa']:
                score += 1

        if ultimo_registro['rsi'] < config.RSI_SOBREVENDA:
            score += 2
        elif ultimo_registro['rsi'] < 50:
            score += 1

        if ultimo_registro['ut_sinal'] == 1:
            score += 1
            if penultimo_registro['ut_sinal'] == -1:
                score += 2

        # 5. Preparar detalhes para o log
        detalhes = {
            'RSI': f"{ultimo_registro['rsi']:.2f}",
            'MA Curta': f"{ultimo_registro['ma_curta']:.8f}",
            'MA Longa': f"{ultimo_registro['ma_longa']:.8f}",
            'UT Signal': "Compra" if ultimo_registro['ut_sinal'] == 1 else "Venda"
        }

        return score, df, detalhes

    except Exception as e:
        return 0, None, {}

def verificar_sinal_recente(df):
    """
    Verifica de forma robusta se um sinal de compra (cruzamento) ocorreu
    dentro do número de candles definido em config.MAX_CANDLES_SINAL_REcente.
    """
    if df is None or len(df) < 2:
        return False

    # Cria colunas 'shifted' no DataFrame completo para evitar erros de borda no slice.
    df_copy = df.copy()
    df_copy['ut_sinal_prev'] = df_copy['ut_sinal'].shift(1)
    df_copy['ma_curta_prev'] = df_copy['ma_curta'].shift(1)
    df_copy['ma_longa_prev'] = df_copy['ma_longa'].shift(1)

    # Analisa apenas os últimos N candles, conforme configuração.
    ultimos_candles = df_copy.tail(config.MAX_CANDLES_SINAL_REcente)

    # Verifica se ocorreu um cruzamento do UT Bot (de -1 para 1) na janela.
    sinal_ut_bot = (ultimos_candles['ut_sinal'] == 1) & (ultimos_candles['ut_sinal_prev'] == -1)

    # Verifica se ocorreu um cruzamento de MAs (curta acima da longa) na janela.
    sinal_cruzamento_ma = (ultimos_candles['ma_curta'] > ultimos_candles['ma_longa']) & \
                          (ultimos_candles['ma_curta_prev'] <= ultimos_candles['ma_longa_prev'])

    # Retorna True se qualquer um dos sinais de cruzamento for encontrado na janela.
    if sinal_ut_bot.any() or sinal_cruzamento_ma.any():
        return True

    return False

def verificar_sinal_chilo_recente(client, symbol: str) -> bool:
    """
    Verifica se a estratégia Chilo RSI emitiu um sinal de compra na vela mais recente.

    Args:
        client: O cliente da API da Binance.
        symbol: O símbolo do ativo a ser analisado.

    Returns:
        True se um sinal de compra ocorreu na última vela, False caso contrário.
    """
    try:
        # 1. Obter dados históricos (klines) - Reutilizando a mesma lógica
        klines = client.get_klines(symbol=symbol, interval=config.TIMEFRAME, limit=300)
        if not klines:
            return False

        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        # 2. Rodar a estratégia Chilo para obter a série de sinais de compra
        _, _, chilo_buy_signals = estrategia_chilo.getChiloStrategy(df)

        # 3. Verificar o sinal na última vela
        if chilo_buy_signals is not None and not chilo_buy_signals.empty:
            # .iloc[-1] acessa o último valor da série
            if chilo_buy_signals.iloc[-1] == True:
                return True

    except Exception as e:
        # Em caso de qualquer erro, consideramos que não há sinal.
        return False

    return False