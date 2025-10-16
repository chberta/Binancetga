# -*- coding: utf-8 -*-

"""
Módulo de Descoberta de Ativos

Este módulo contém as funções responsáveis por encontrar e classificar
os melhores pares de criptomoedas para análise, usando diferentes critérios
como volume de negociação e capitalização de mercado.
"""

import pandas as pd
import requests
import config
from binance.client import Client
from logger_setup import logger

def get_tradable_spot_symbols(client: Client) -> set:
    """Busca todos os símbolos SPOT que estão atualmente em negociação."""
    logger.info("Buscando informações de todos os ativos na Binance...")
    exchange_info = client.get_exchange_info()
    symbols_data = exchange_info['symbols']

    logger.info("Filtrando por ativos de qualidade (SPOT, TRADING, par USDT)...")
    tradable_symbols = {
        s['symbol'] for s in symbols_data
        if 'SPOT' in s.get('permissionSets', [[]])[0]
        and s['status'] == 'TRADING'
        and s['symbol'].endswith('USDT')
    }
    logger.info(f"Encontrados {len(tradable_symbols)} ativos SPOT/USDT negociáveis.")
    return tradable_symbols

def discover_top_by_volume(client: Client, tradable_symbols: set) -> list:
    """Descobre os principais pares por volume dentro de uma lista de negociáveis."""
    logger.info("Buscando dados de volume (ticker 24h)...")
    all_tickers = client.get_ticker()
    df_tickers = pd.DataFrame(all_tickers)

    # Filtra apenas os símbolos que são negociáveis
    df_tickers = df_tickers[df_tickers['symbol'].isin(tradable_symbols)]

    df_tickers['quoteVolume'] = pd.to_numeric(df_tickers['quoteVolume'])
    top_volume_pairs = df_tickers.sort_values(by='quoteVolume', ascending=False)

    logger.info(f"Rankeados {len(top_volume_pairs)} pares por volume.")
    return top_volume_pairs['symbol'].tolist()

def discover_top_by_marketcap(tradable_symbols: set) -> list:
    """Descobre os principais pares por Market Cap e cruza com os negociáveis."""
    logger.info("Buscando ranking de Market Cap da CoinGecko...")
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": 1}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        gecko_coins = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao buscar dados da CoinGecko: {e}")
        return []

    ranked_symbols = []
    for coin in gecko_coins:
        symbol = f"{coin['symbol'].upper()}USDT"
        if symbol in tradable_symbols:
            ranked_symbols.append(symbol)

    logger.info(f"Encontrados e rankeados {len(ranked_symbols)} símbolos da CoinGecko na Binance.")
    return ranked_symbols