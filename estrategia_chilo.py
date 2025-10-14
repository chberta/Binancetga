import pandas as pd
import numpy as np
import config

def getChiloStrategy(stock_data: pd.DataFrame):
    """
    Calcula o indicador Custom HiLo e retorna uma decisão de trade e detalhes.
    """
    # Usar parâmetros do config
    length = config.CHILO_LENGTH
    offset = config.CHILO_OFFSET
    hilo_type = config.CHILO_HILO_TYPE
    ma_type = config.CHILO_MA_TYPE

    df = stock_data.copy()

    min_required = length + offset + 1
    if len(df) < min_required:
        return False, {}

    # Médias de high/low
    if ma_type.upper() == "EMA":
        hima = df["high"].ewm(span=length, adjust=False).mean()
        loma = df["low"].ewm(span=length, adjust=False).mean()
    else:
        hima = df["high"].rolling(window=length).mean()
        loma = df["low"].rolling(window=length).mean()

    simple_hilo = hilo_type == "HiLo"

    if not simple_hilo:
        hihi = df["high"].rolling(window=length).max()
        lolo = df["low"].rolling(window=length).min()
    else:
        hihi = lolo = pd.Series(np.nan, index=df.index)

    hilo = pd.Series(index=df.index, dtype=float)

    for i in range(len(df)):
        if i < length + offset:
            hilo.iloc[i] = np.nan
            continue

        close_i = df["close"].iat[i]
        hima_off = hima.iat[i - offset]
        loma_off = loma.iat[i - offset]

        # Checar se os valores são válidos antes de usar
        if pd.isna(hima_off) or pd.isna(loma_off):
            hilo.iloc[i] = hilo.iat[i - 1] if i > 0 else np.nan
            continue

        if simple_hilo:
            if close_i < loma_off:
                hilo_val = hima.iat[i]
            elif close_i > hima_off:
                hilo_val = loma.iat[i]
            else:
                hilo_val = hilo.iat[i - 1] if i > 0 else np.nan
        else:
            if close_i < loma_off:
                hilo_val = hihi.iat[i]
            elif close_i > hima_off:
                hilo_val = lolo.iat[i]
            else:
                hilo_val = hilo.iat[i - 1] if i > 0 else np.nan

        hilo.iloc[i] = hilo_val

    # Sinais de cruzamento
    buy_arith = np.sign(df["close"] - hima.shift(offset))
    sell_arith = np.sign(df["close"] - loma.shift(offset))

    buy = (buy_arith.shift(1) <= 0.5) & (buy_arith > 0.5)
    sell = (sell_arith.shift(1) >= -0.5) & (sell_arith < -0.5)

    buy_state = pd.Series(False, index=df.index)
    for i in range(1, len(df)):
        if buy.iat[i]:
            buy_state.iat[i] = True
        elif sell.iat[i]:
            buy_state.iat[i] = False
        else:
            buy_state.iat[i] = buy_state.iat[i - 1]

    # Checagem final para evitar erros se os dados forem insuficientes para os últimos valores
    if hima.iat[-1] is np.nan or loma.iat[-1] is np.nan or hilo.iat[-1] is np.nan:
        return False, {}

    chilo_trade_decision = bool(buy_state.iat[-1])

    detalhes = {
        'Chilo HiMA': f"{hima.iat[-1]:.8f}",
        'Chilo LoMA': f"{loma.iat[-1]:.8f}",
        'Chilo HiLo': f"{hilo.iat[-1]:.8f}",
        'Chilo Decisão': 'Comprar' if chilo_trade_decision else 'Vender'
    }

    return chilo_trade_decision, detalhes