# -*- coding: utf-8 -*-

"""
Módulo Position Manager

Este módulo é responsável por gerenciar as posições de trade que já estão abertas.
Ele verifica os preços atuais, calcula lucros/perdas e decide quando vender
com base nas estratégias de Take Profit e Stop Loss.
"""

import config
from binance.client import Client
from logger_setup import logger

def check_active_positions(client, active_trades: list):
    """
    Verifica as posições ativas para determinar se alguma deve ser vendida.

    Args:
        client: O cliente da API da Binance.
        active_trades: Uma lista de dicionários, onde cada um representa um trade ativo.

    Returns:
        Uma lista de trades que foram atualizados (ex: status alterado para 'CLOSED').
    """
    if not active_trades:
        logger.info("Nenhuma posição ativa para verificar.")
        return []

    logger.info(f"Iniciando verificação de {len(active_trades)} posições ativas...")

    updated_trades = []
    for trade in active_trades:
        try:
            symbol = trade['symbol']
            logger.debug(f"Verificando preço atual de {symbol}...")

            # Lógica de verificação de Take Profit e Stop Loss será implementada aqui no futuro.
            # Por enquanto, apenas logamos a verificação.

            # Exemplo de como obter o preço atual:
            # ticker = client.get_symbol_ticker(symbol=symbol)
            # current_price = float(ticker['price'])
            # entry_price = trade['entry_price']
            # pnl = ((current_price - entry_price) / entry_price) * 100
            # logger.info(f"Posição {symbol}: Preço de Entrada: {entry_price}, Preço Atual: {current_price}, PnL: {pnl:.2f}%")

        except Exception as e:
            logger.error(f"Erro ao verificar a posição ativa para {trade.get('symbol', 'N/A')}: {e}")

    logger.info("Verificação de posições ativas concluída.")
    return updated_trades