# -*- coding: utf-8 -*-

"""
Módulo Gerenciador de Ordens

Responsável por toda a interação com a API de ordens da Binance.
Isso inclui colocar, verificar, cancelar e gerenciar ordens de compra e venda.
"""

import time
import config
import state_manager
from binance.client import Client
from binance.exceptions import BinanceAPIException
from logger_setup import logger

def _get_lot_size_precision(symbol_info: dict) -> int:
    """Extrai a precisão de quantidade (lot size) dos filtros do símbolo."""
    for f in symbol_info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step_size = f['stepSize']
            # A precisão é o número de casas decimais do stepSize
            return len(step_size.split('.')[1].rstrip('0')) if '.' in step_size else 0
    return 0

def abrir_novo_trade(client: Client, trade: dict):
    """Orquestra o processo completo de abertura de um novo trade."""
    symbol = trade['symbol']
    logger.info(f"Iniciando processo de abertura de trade para {symbol}...")

    try:
        symbol_info = client.get_symbol_info(symbol)
        precision = _get_lot_size_precision(symbol_info)

        depth = client.get_order_book(symbol=symbol, limit=5)
        if not depth or not depth.get('asks') or not depth['asks'][0]:
            logger.error(f"Book de ofertas para {symbol} está vazio ou inválido.")
            state_manager.remover_trade(symbol)
            return False

        best_ask_price = float(depth['asks'][0][0])
        logger.info(f"Melhor preço de venda (Best Ask): {best_ask_price:.8f}")

        quantity = config.VALOR_OPERACAO_USDT / best_ask_price
        quantity_rounded = round(quantity, precision)
        logger.info(f"Quantidade calculada: {quantity_rounded}")

        logger.info("Enviando ordem LIMIT de teste...")
        try:
            order = client.create_test_order(
                symbol=symbol, side=Client.SIDE_BUY, type=Client.ORDER_TYPE_LIMIT,
                timeInForce=Client.TIME_IN_FORCE_GTC, quantity=quantity_rounded,
                price=f'{best_ask_price:.8f}'
            )
            logger.info("Ordem de teste LIMIT enviada com sucesso.")
            trade['order_id'] = f"test_{int(time.time())}"
        except BinanceAPIException as e:
            logger.warning(f"ERRO ao enviar ordem LIMIT: {e}. Tentando ordem MARKET.")
            order = client.create_test_order(
                symbol=symbol, side=Client.SIDE_BUY, type=Client.ORDER_TYPE_MARKET,
                quantity=quantity_rounded
            )
            logger.info("Ordem de teste MARKET enviada com sucesso.")
            trade['order_id'] = f"test_{int(time.time())}"

        logger.info("[SIMULAÇÃO] Ordem considerada executada (FILLED).")
        entry_price = best_ask_price

        trade.update({
            "status": "ACTIVE", "entry_price": entry_price, "quantity": quantity_rounded,
            "initial_stop_price": entry_price * (1 - (config.TRAILING_STOP_PERCENT / 100)),
            "trailing_stop_price": entry_price * (1 - (config.TRAILING_STOP_PERCENT / 100))
        })

        trades_ativos = state_manager.ler_trades_ativos()
        for i, t in enumerate(trades_ativos):
            if t['symbol'] == symbol:
                trades_ativos[i] = trade
                state_manager.escrever_trades_ativos(trades_ativos)
                logger.info(f"Trade para {symbol} atualizado para ACTIVE na memória.")
                return True

    except BinanceAPIException as e:
        logger.error(f"ERRO DE API ao tentar abrir trade para {symbol}: {e}")
        state_manager.remover_trade(symbol)
        return False
    except Exception as e:
        logger.error(f"ERRO inesperado ao abrir trade para {symbol}: {e}")
        state_manager.remover_trade(symbol)
        return False

    return False