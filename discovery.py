# -*- coding: utf-8 -*-

"""
Módulo de Descoberta de Ativos

Contém funções para encontrar e classificar os melhores pares para análise.
"""

import pandas as pd
from binance.client import Client
from logger_setup import logger
import config
from datetime import datetime, timedelta

def get_tradable_spot_symbols(client: Client) -> set:
    """
    Busca todos os símbolos SPOT que estão atualmente em negociação,
    usando um filtro robusto para garantir a qualidade dos ativos.
    """
    logger.info("Buscando informações de todos os ativos na Binance...")
    try:
        exchange_info = client.get_exchange_info()
        symbols_data = exchange_info['symbols']
    except Exception as e:
        logger.error(f"Não foi possível buscar os dados da exchange: {e}")
        return set()

    logger.info("Filtrando por ativos de qualidade (SPOT, TRADING, par USDT, não-alavancado)...")

    tradable_symbols = set()
    for s in symbols_data:
        # Condições para um ativo ser considerado válido e seguro para a nossa estratégia
        if (s.get('status') == 'TRADING' and
            s.get('isSpotTradingAllowed') and
            s.get('quoteAsset') == 'USDT' and
            # Filtra tokens de alavancagem (ex: BTCUP, ETHDOWN) e outros indesejados
            'UP' not in s.get('baseAsset', '') and
            'DOWN' not in s.get('baseAsset', '') and
            'BEAR' not in s.get('baseAsset', '') and
            'BULL' not in s.get('baseAsset', '')):
            tradable_symbols.add(s['symbol'])

    logger.info(f"Encontrados {len(tradable_symbols)} ativos SPOT/USDT negociáveis e qualificados.")
    return tradable_symbols

def discover_top_by_volume(client: Client, tradable_symbols: set) -> list:
    """Descobre os 100 principais pares por volume dentro de uma lista de negociáveis."""
    logger.info("Buscando dados de volume (ticker 24h)...")
    try:
        all_tickers = client.get_ticker()
    except Exception as e:
        logger.error(f"Não foi possível buscar os dados de volume (ticker): {e}")
        return []

    df_tickers = pd.DataFrame(all_tickers)

    df_tickers = df_tickers[df_tickers['symbol'].isin(tradable_symbols)]

    df_tickers['quoteVolume'] = pd.to_numeric(df_tickers['quoteVolume'])
    top_volume_pairs = df_tickers.sort_values(by='quoteVolume', ascending=False).head(config.TOP_N_VOLUME)

    logger.info(f"Selecionados os {len(top_volume_pairs)} principais pares por volume.")
    return top_volume_pairs['symbol'].tolist()

def filter_assets_by_age(client: Client, symbols: list, min_weeks_old: int = 52) -> list:
    """Filtra uma lista de símbolos, mantendo apenas aqueles com mais de X semanas."""
    logger.info(f"Iniciando filtro de idade para {len(symbols)} símbolos...")
    long_lived_symbols = []
    cutoff_date = datetime.now() - timedelta(weeks=min_weeks_old)

    for symbol in symbols:
        try:
            first_kline = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1DAY, startTime=0, limit=1)
            if first_kline:
                kline_date = datetime.fromtimestamp(first_kline[0][0] / 1000)
                if kline_date < cutoff_date:
                    long_lived_symbols.append(symbol)
        except Exception as e:
            logger.error(f"Erro ao processar o símbolo {symbol} no filtro de idade: {e}")
            continue

    logger.info(f"Filtro de idade concluído. {len(long_lived_symbols)}/{len(symbols)} símbolos atendem ao critério.")
    return long_lived_symbols
