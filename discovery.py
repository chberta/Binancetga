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

def discover_top_by_volume(client: Client) -> list:
    """
    Descobre os principais pares por volume de negociação na Binance.
    Usa os dados de `get_exchange_info` para garantir que são ativos SPOT.
    """
    print("Buscando informações de todos os ativos na Binance...")
    exchange_info = client.get_exchange_info()
    symbols_data = exchange_info['symbols']

    print("Filtrando por ativos de qualidade (SPOT, TRADING, par USDT)...")
    ativos_spot_usdt = []
    for s in symbols_data:
        if 'SPOT' in s.get('permissionSets', [[]])[0] and s['status'] == 'TRADING' and s['symbol'].endswith('USDT'):
            ativos_spot_usdt.append(s['symbol'])

    print("Buscando dados de volume (ticker 24h)...")
    all_tickers = client.get_ticker()
    df_tickers = pd.DataFrame(all_tickers)
    df_tickers = df_tickers[df_tickers['symbol'].isin(ativos_spot_usdt)]

    df_tickers['quoteVolume'] = pd.to_numeric(df_tickers['quoteVolume'])
    top_volume_pairs = df_tickers.sort_values(by='quoteVolume', ascending=False)

    return top_volume_pairs['symbol'].tolist()


def discover_top_by_marketcap(client: Client) -> list:
    """
    Descobre os principais pares por capitalização de mercado usando a API da CoinGecko
    e cruza com os pares existentes na Binance.
    """
    print("Buscando ranking de Market Cap da CoinGecko...")
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        gecko_coins = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar dados da CoinGecko: {e}")
        return []

    # Pega todos os símbolos USDT da Binance para cruzamento
    exchange_info = client.get_exchange_info()
    binance_usdt_symbols = {s['baseAsset'].upper(): s['symbol'] for s in exchange_info['symbols'] if s['symbol'].endswith('USDT')}

    ranked_symbols = []
    for coin in gecko_coins:
        base_asset = coin['symbol'].upper()
        if base_asset in binance_usdt_symbols:
            ranked_symbols.append(binance_usdt_symbols[base_asset])

    print(f"Encontrados e rankeados {len(ranked_symbols)} símbolos da CoinGecko na Binance.")
    return ranked_symbols