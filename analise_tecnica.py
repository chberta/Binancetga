# -*- coding: utf-8 -*-

import config
import pandas as pd
import ta
from ta.utils import dropna

def calcular_ut_bot(high, low, close, periodo=config.UT_BOT_PERIODO, multiplicador=config.UT_BOT_ATR_MULTIPLICADOR):
    """
    Calcula o indicador UT Bot Alerts.
    Retorna uma série com a linha de stop e a direção do sinal (1 para compra, -1 para venda).
    """
    atr = ta.volatility.average_true_range(high, low, close, window=periodo)

    # A Média Móvel Exponencial (EMA) é comumente usada no UT Bot
    ema = ta.trend.ema_indicator(close, window=periodo)

    trailing_stop = pd.Series(index=close.index, dtype=float)
    sinal = pd.Series(index=close.index, dtype=int)

    # Inicializa os primeiros valores para evitar erro no loop
    if not close.empty:
        trailing_stop.iloc[0] = ema.iloc[0] - multiplicador * atr.iloc[0]
        sinal.iloc[0] = 1

    for i in range(1, len(close)):
        if close[i] > trailing_stop.iloc[i-1]:
            sinal.iloc[i] = 1 # Sinal de compra
            trailing_stop.iloc[i] = max(trailing_stop.iloc[i-1], ema.iloc[i] - multiplicador * atr.iloc[i])
        else:
            sinal.iloc[i] = -1 # Sinal de venda
            trailing_stop.iloc[i] = min(trailing_stop.iloc[i-1], ema.iloc[i] + multiplicador * atr.iloc[i])

    return trailing_stop, sinal

def calcular_score_ativo(client, symbol):
    """
    Calcula o score de um único ativo com base em indicadores técnicos.
    """
    try:
        # 1. Obter dados históricos (klines)
        # Pegamos um pouco mais de dados para garantir que os indicadores sejam calculados corretamente
        klines = client.get_klines(symbol=symbol, interval=config.TIMEFRAME, limit=200)
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])

        # Converter colunas para numérico
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])

        # 2. Calcular Indicadores
        df['ma_curta'] = ta.trend.sma_indicator(df['close'], window=config.MA_CURTA)
        df['ma_longa'] = ta.trend.sma_indicator(df['close'], window=config.MA_LONGA)
        df['rsi'] = ta.momentum.rsi(df['close'], window=config.RSI_PERIODO)
        df['ut_stop'], df['ut_sinal'] = calcular_ut_bot(df['high'], df['low'], df['close'])

        df.dropna(inplace=True)
        if df.empty:
            return 0 # Não há dados suficientes

        # 3. Lógica de Score
        score = 0
        ultimo_registro = df.iloc[-1]
        penultimo_registro = df.iloc[-2]

        # Score de Média Móvel (Cruzamento ou tendência)
        if ultimo_registro['ma_curta'] > ultimo_registro['ma_longa']:
            score += 1 # Tendência de alta
            if penultimo_registro['ma_curta'] <= penultimo_registro['ma_longa']:
                score += 1 # Cruzamento recente para cima (Golden Cross)

        # Score de RSI
        if ultimo_registro['rsi'] < config.RSI_SOBREVENDA:
            score += 2 # Sobre-vendido, forte sinal de compra
        elif ultimo_registro['rsi'] < 50:
            score += 1 # Abaixo da linha central, potencial de alta

        # Score do UT Bot
        if ultimo_registro['ut_sinal'] == 1:
            score += 1 # Sinal de compra ativo
            if penultimo_registro['ut_sinal'] == -1:
                score += 2 # Novo sinal de compra

        return score, df

    except Exception as e:
        # print(f"Erro ao calcular score para {symbol}: {e}")
        return 0, None

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