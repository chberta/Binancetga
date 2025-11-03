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
from datetime import datetime, timedelta

def get_tradable_spot_symbols(client: Client) -> set:
    """Busca todos os símbolos SPOT que estão atualmente em negociação."""
    logger.info("Buscando informações de todos os ativos na Binance...")
    exchange_info = client.get_exchange_info()
    symbols_data = exchange_info['symbols']

    logger.info("Filtrando por ativos de qualidade (SPOT, TRADING, par USDT)...")
    tradable_symbols = {
        s['symbol'] for s in symbols_data
        # Garante que o ativo tem permissões e que 'SPOT' é uma delas.
        if s.get('permissions') and 'SPOT' in s['permissions']
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
    # Ordena e seleciona os 100 primeiros
    top_100_volume_pairs = df_tickers.sort_values(by='quoteVolume', ascending=False).head(100)

    logger.info(f"Selecionados os 100 principais pares por volume.")
    return top_100_volume_pairs['symbol'].tolist()

def filter_assets_by_age(client: Client, symbols: list, min_weeks_old: int = 52) -> list:
    """
    Filtra uma lista de símbolos, mantendo apenas aqueles que existem há um
    número mínimo de semanas.

    Args:
        client: O cliente da API da Binance.
        symbols: A lista de símbolos a ser filtrada.
        min_weeks_old: O número mínimo de semanas de existência do ativo.

    Returns:
        Uma lista de símbolos que atendem ao critério de idade.
    """
    logger.info(f"Iniciando filtro de idade para {len(symbols)} símbolos (mínimo de {min_weeks_old} semanas)...")
    long_lived_symbols = []
    cutoff_date = datetime.now() - timedelta(weeks=min_weeks_old)

    for symbol in symbols:
        try:
            # Busca o primeiro kline (vela) já registrado para o símbolo.
            # startTime=0 é uma forma de pedir desde o início dos tempos na Binance.
            # O timestamp precisa ser um inteiro de milissegundos.
            first_kline = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1DAY, startTime=0, limit=1)

            if first_kline:
                # O timestamp do kline vem em milissegundos, então dividimos por 1000.
                kline_timestamp_ms = first_kline[0][0]
                kline_date = datetime.fromtimestamp(kline_timestamp_ms / 1000)

                if kline_date < cutoff_date:
                    long_lived_symbols.append(symbol)
            else:
                logger.warning(f"Não foi possível obter o histórico de klines para {symbol}. O ativo pode ser novo demais ou inválido.")

        except Exception as e:
            logger.error(f"Erro ao processar o símbolo {symbol} no filtro de idade: {e}")
            # Continua para o próximo símbolo em caso de erro.
            continue

    logger.info(f"Filtro de idade concluído. {len(long_lived_symbols)}/{len(symbols)} símbolos atendem ao critério.")
    return long_lived_symbols