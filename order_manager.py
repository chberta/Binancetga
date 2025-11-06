# -*- coding: utf-8 -*-

"""
Módulo Order Manager

Este módulo é responsável por todas as interações relacionadas a ordens com a API da Binance.
Ele lida com a criação, cancelamento e verificação de ordens de compra e venda.
"""

import config
from binance.client import Client
from binance.exceptions import BinanceAPIException
from logger_setup import logger, trades_logger
import math

def _get_lot_size_precision(symbol_info: dict) -> tuple[float, int]:
    """Extrai o stepSize e a precisão do filtro LOT_SIZE."""
    for f in symbol_info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step_size = float(f['stepSize'])
            precision = int(round(-math.log(step_size, 10), 0))
            return step_size, precision
    return 0.0, 0 # Fallback

def _get_price_precision(symbol_info: dict) -> int:
    """Extrai a precisão do preço do filtro PRICE_FILTER."""
    for f in symbol_info['filters']:
        if f['filterType'] == 'PRICE_FILTER':
            tick_size = float(f['tickSize'])
            # A precisão é o número de casas decimais do tickSize
            precision = int(round(-math.log(tick_size, 10), 0))
            return precision
    return 8 # Um fallback comum para preços cripto

def place_buy_order(client, symbol: str, quote_order_qty: float):
    """
    Coloca uma ordem de compra a mercado (real ou de teste), buscando o preço real,
    calculando a quantidade correta e retornando os dados da transação.
    """
    try:
        mode = "REAL" if config.MODO_REAL else "TESTE"
        logger.info(f"Iniciando colocação de ordem de compra MODO {mode} para {symbol} com {quote_order_qty} USDT.")

        # 1. Obter o preço de compra atual do livro de ordens (melhor ask)
        order_book = client.get_order_book(symbol=symbol, limit=5)
        if not order_book.get('asks'):
            logger.error(f"Livro de ordens para {symbol} está vazio. Não é possível determinar o preço.")
            return None
        entry_price = float(order_book['asks'][0][0])
        logger.info(f"Preço de entrada (melhor ask) para {symbol} é {entry_price:.8f} USDT.")

        # 2. Calcular e formatar a quantidade de acordo com as regras de precisão do símbolo
        symbol_info = client.get_symbol_info(symbol)
        step_size, precision = _get_lot_size_precision(symbol_info)
        if step_size == 0.0:
            logger.error(f"Não foi possível encontrar o stepSize para {symbol}.")
            return None

        quantity = quote_order_qty / entry_price
        # Arredonda a quantidade para baixo para o múltiplo de step_size mais próximo para evitar erros
        quantity = math.floor(quantity / step_size) * step_size

        # Garante que a quantidade final seja um float com a precisão correta
        formatted_quantity = float(f"{quantity:.{precision}f}")
        price_precision = _get_price_precision(symbol_info)

        logger.info(f"Quantidade calculada para {symbol}: {formatted_quantity}")

        # 3. Executar a ordem (Real ou Teste)
        if config.MODO_REAL:
            logger.warning(f"MODO REAL ATIVADO. Executando ordem de compra real para {symbol}.")
            order = client.create_order(
                symbol=symbol,
                side=Client.SIDE_BUY,
                type=Client.ORDER_TYPE_MARKET,
                quantity=formatted_quantity
            )
            # Para uma ordem real, calculamos o preço médio de execução a partir dos 'fills'
            fills = order.get('fills', [])
            if not fills:
                logger.error("Ordem real não teve 'fills'. Não é possível determinar o preço de entrada.")
                return None

            avg_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / float(order['executedQty'])
            total_quantity = float(order['executedQty'])
            logger.info(f"Ordem de compra REAL para {symbol} executada. Preço médio: {avg_price}, Quantidade: {total_quantity}")
            trades_logger.info(f"BUY,{symbol},{avg_price:.{price_precision}f},{total_quantity}")
            return {"status": "SUCCESS", "symbol": symbol, "entry_price": avg_price, "quantity": total_quantity}
        else:
            logger.info("MODO DE TESTE. Executando create_test_order.")
            client.create_test_order(
                symbol=symbol,
                side=Client.SIDE_BUY,
                type=Client.ORDER_TYPE_MARKET,
                quantity=formatted_quantity
            )
            logger.info(f"Ordem de compra de TESTE para {symbol} foi bem-sucedida (simulação).")
            trades_logger.info(f"BUY,{symbol},{entry_price:.{price_precision}f},{formatted_quantity}")
            # Retorna os dados como se a ordem tivesse sido executada pelo preço do order book
            return {"status": "TEST_SUCCESS", "symbol": symbol, "entry_price": entry_price, "quantity": formatted_quantity}

    except BinanceAPIException as e:
        logger.error(f"Erro da API da Binance ao tentar colocar ordem para {symbol}: {e}")
        return None
    except Exception as e:
        logger.error(f"Ocorreu um erro inesperado ao colocar ordem para {symbol}: {e}", exc_info=True)
        return None

def place_sell_order(client, symbol: str, quantity: float):
    """
    Coloca uma ordem de venda a mercado (real ou de teste).
    """
    try:
        mode = "REAL" if config.MODO_REAL else "TESTE"
        logger.info(f"Iniciando colocação de ordem de venda MODO {mode} para {symbol} (Quantidade: {quantity}).")

        # Formatar a quantidade para garantir que atenda às regras de precisão do símbolo
        symbol_info = client.get_symbol_info(symbol)
        step_size, precision = _get_lot_size_precision(symbol_info)
        if step_size == 0.0:
            logger.error(f"Não foi possível encontrar o stepSize para {symbol} na venda.")
            return None

        # Arredonda a quantidade para baixo para o múltiplo de step_size mais próximo
        quantity = math.floor(quantity / step_size) * step_size
        formatted_quantity = float(f"{quantity:.{precision}f}")

        logger.info(f"Quantidade de venda formatada para {symbol}: {formatted_quantity}")

        if config.MODO_REAL:
            logger.warning(f"MODO REAL ATIVADO. Executando ordem de venda real para {symbol}.")
            order = client.create_order(
                symbol=symbol,
                side=Client.SIDE_SELL,
                type=Client.ORDER_TYPE_MARKET,
                quantity=formatted_quantity
            )
            # Para uma ordem real, o preço de venda é o preço médio dos 'fills'
            fills = order.get('fills', [])
            if fills:
                avg_price = sum(float(fill['price']) * float(fill['qty']) for fill in fills) / float(order['executedQty'])
                # Opcional: pode-se retornar o avg_price se necessário no futuro

            return {"status": "SUCCESS", "order_id": order.get('orderId', 'N/A')}
        else:
            logger.info("MODO DE TESTE. Executando create_test_order para venda.")
            client.create_test_order(
                symbol=symbol,
                side=Client.SIDE_SELL,
                type=Client.ORDER_TYPE_MARKET,
                quantity=formatted_quantity
            )
            logger.info(f"Ordem de venda de TESTE para {symbol} foi bem-sucedida (simulação).")
            return {"status": "TEST_SUCCESS"}

    except BinanceAPIException as e:
        logger.error(f"Erro da API da Binance ao tentar vender {symbol}: {e}")
        return None
    except Exception as e:
        logger.error(f"Ocorreu um erro inesperado ao vender {symbol}: {e}", exc_info=True)
        return None