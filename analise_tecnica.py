# -*- coding: utf-8 -*-

import config
import pandas as pd
import ta
from ta.utils import dropna

def calcular_ut_bot(high, low, close, periodo=config.UT_BOT_PERIODO, multiplicador=config.UT_BOT_ATR_MULTIPLICADOR):
    """
    Calcula o indicador UT Bot Alerts de forma robusta, lidando com NaNs.
    """
    atr = ta.volatility.average_true_range(high, low, close, window=periodo)
    ema = ta.trend.ema_indicator(close, window=periodo)

    trailing_stop = pd.Series(index=close.index, dtype=float)
    sinal = pd.Series(index=close.index, dtype=float)

    first_valid_index = ema.first_valid_index()
    if first_valid_index is None:
        return trailing_stop, sinal

    sinal.loc[first_valid_index] = 1.0
    trailing_stop.loc[first_valid_index] = ema.loc[first_valid_index] - multiplicador * atr.loc[first_valid_index]

    for i in range(close.index.get_loc(first_valid_index) + 1, len(close)):
        prev_trailing_stop = trailing_stop.iloc[i-1]

        if pd.isna(prev_trailing_stop):
            # Se o valor anterior for NaN, não podemos continuar
            continue

        if close.iloc[i] > prev_trailing_stop:
            sinal.iloc[i] = 1.0
            current_stop_value = ema.iloc[i] - multiplicador * atr.iloc[i]
            trailing_stop.iloc[i] = max(prev_trailing_stop, current_stop_value)
        else:
            sinal.iloc[i] = -1.0
            current_stop_value = ema.iloc[i] + multiplicador * atr.iloc[i]
            trailing_stop.iloc[i] = min(prev_trailing_stop, current_stop_value)

    return trailing_stop, sinal

def calcular_score_ativo(client, symbol):
    """
    Calcula o score de um único ativo e retorna detalhes dos indicadores.
    Retorna: score (int), df (DataFrame), detalhes (dict)
    """
    try:
        # 1. Obter dados históricos (klines)
        klines = client.get_klines(symbol=symbol, interval=config.TIMEFRAME, limit=200)
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

        # 3. Lógica de Score
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

        # 4. Preparar detalhes para o log
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
    Verifica se o sinal de compra ocorreu dentro do número de candles definido em config.
    """
    if df is None or len(df) < 2:
        return False

    # Analisa os últimos N candles, conforme configuração
    ultimos_candles = df.tail(config.MAX_CANDLES_SINAL_REcente)

    # Exemplo de verificação: Houve um cruzamento do UT Bot nos últimos N candles?
    sinal_ut_bot = (ultimos_candles['ut_sinal'] == 1) & (ultimos_candles['ut_sinal'].shift(1) == -1)

    # Exemplo 2: Houve um cruzamento de médias nos últimos N candles?
    sinal_cruzamento_ma = (ultimos_candles['ma_curta'] > ultimos_candles['ma_longa']) & \
                          (ultimos_candles['ma_curta'].shift(1) <= ultimos_candles['ma_longa'].shift(1))

    if sinal_ut_bot.any() or sinal_cruzamento_ma.any():
        return True

    return False