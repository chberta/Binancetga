# -*- coding: utf-8 -*-

"""
Módulo Position Manager

Gerencia posições abertas, verificando preços e decidindo vendas com base
nas estratégias de Stop Loss, Trailing Stop e Take Profit.
"""

import config
import state_manager
import order_manager
from logger_setup import logger

def _handle_sell(client, trade: dict, reason: str, pnl: float):
    """
    Centraliza a lógica de venda de uma posição, seja por Stop Loss,
    Trailing Stop ou Take Profit.
    """
    symbol = trade['symbol']
    quantity = trade['quantity']

    logger.info(f"ORDEM DE VENDA para {symbol}. Motivo: {reason}. PnL: {pnl:.2f}%.")

    # Coloca a ordem de venda
    sell_result = order_manager.place_sell_order(client, symbol, quantity)

    # Se a ordem for bem-sucedida, remove o trade da memória.
    if sell_result:
        state_manager.remover_trade(symbol)
        logger.info(f"Trade para {symbol} fechado e removido da memória com sucesso.")
        return True
    else:
        logger.error(f"FALHA ao executar a ordem de venda para {symbol}. O trade permanecerá ativo para nova tentativa.")
        return False

def check_active_positions(client, active_trades: list):
    """
    Verifica as posições ativas para determinar se alguma deve ser vendida.
    A ordem de verificação é crucial:
    1. Stop Loss Fixo (proteção inicial)
    2. Trailing Stop Loss (proteção de lucros)
    3. Take Profit (realização de lucros)
    """
    if not active_trades:
        return

    logger.info(f"Iniciando verificação de {len(active_trades)} posições ativas...")

    # Obtém os preços de todos os tickers de uma vez para eficiência
    try:
        tickers = {ticker['symbol']: float(ticker['price']) for ticker in client.get_all_tickers()}
    except Exception as e:
        logger.error(f"Não foi possível obter os preços dos tickers: {e}")
        return

    for trade in active_trades:
        symbol = trade.get('symbol')
        if not symbol or symbol not in tickers:
            continue

        current_price = tickers[symbol]
        entry_price = trade.get('entry_price', 0)
        if entry_price == 0:
            continue

        pnl = ((current_price - entry_price) / entry_price) * 100

        # --- 1. Verificação de Stop Loss Fixo ---
        # A proteção mais importante. Vende se o preço cair abaixo do limite.
        stop_loss_price = entry_price * (1 - config.STOP_LOSS_PERCENT / 100)
        if current_price <= stop_loss_price:
            _handle_sell(client, trade, "STOP LOSS", pnl)
            continue # Move para o próximo trade

        # --- 2. Verificação de Trailing Stop Loss ---
        # Ativado apenas quando a operação está no lucro.
        trailing_stop_activation_price = entry_price * (1 + config.TRAILING_STOP_PERCENT / 100)

        if current_price > trailing_stop_activation_price:
            # Calcula o novo preço do trailing stop
            new_trailing_stop = current_price * (1 - config.TRAILING_STOP_PERCENT / 100)

            # Se o novo stop for maior que o antigo, atualiza
            # O 'trailing_stop_price' é salvo no próprio objeto do trade em memória
            last_trailing_stop = trade.get('trailing_stop_price', 0)
            if new_trailing_stop > last_trailing_stop:
                trade['trailing_stop_price'] = new_trailing_stop
                logger.debug(f"TRAILING STOP para {symbol} atualizado para {new_trailing_stop:.8f}")

        # Se o trailing stop já foi ativado, verifica se foi atingido
        if 'trailing_stop_price' in trade:
            if current_price <= trade['trailing_stop_price']:
                _handle_sell(client, trade, "TRAILING STOP", pnl)
                continue

        # --- 3. Verificação de Take Profit ---
        # Lógica de realização de lucros (parcial ou total)
        # TODO: Implementar a lógica de Take Profit parcial se necessário.
        # Por enquanto, usamos um take profit total simples.
        if hasattr(config, 'TAKE_PROFIT_PERCENT') and isinstance(config.TAKE_PROFIT_PERCENT, (int, float)):
             if pnl >= config.TAKE_PROFIT_PERCENT:
                _handle_sell(client, trade, "TAKE PROFIT", pnl)
                continue

    # Ao final do loop, salva quaisquer alterações nos trades (como o trailing_stop_price)
    state_manager.escrever_trades_ativos(active_trades)
    logger.info("Verificação de posições ativas concluída.")
