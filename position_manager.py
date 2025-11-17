# -*- coding: utf-8 -*-

"""
Módulo Position Manager

Gerencia posições abertas, verificando preços e decidindo vendas com base
nas estratégias de Stop Loss, Trailing Stop e Take Profit Parcial.
"""

import config
import state_manager
import order_manager
from logger_setup import logger, trades_logger

from datetime import datetime

def _handle_full_sell(client, trade: dict, reason: str, pnl: float, current_price: float):
    """
    Tenta vender 100% de uma posição.
    Retorna True se a ordem de venda foi bem-sucedida, False caso contrário.
    A remoção do trade da lista de ativos é gerenciada pelo chamador.
    """
    symbol = trade['symbol']
    quantity = trade['quantity']

    proporcao_restante = quantity / trade['initial_quantity']
    pnl_usdt = (pnl / 100) * (config.VALOR_OPERACAO_USDT * proporcao_restante)

    logger.info(f"ORDEM DE VENDA TOTAL para {symbol}. Motivo: {reason}. PnL: {pnl:.2f}% ({pnl_usdt:+.2f} USDT).")

    # Novo formato de log
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = (f"[{timestamp}] SELL (Close) | Symbol: {symbol} | Price: {current_price} | Reason: {reason} | "
               f"PnL: {pnl:+.2f}% ({pnl_usdt:+.2f} USDT) | Qty Sold: {quantity}")
    trades_logger.info(log_msg)

    if order_manager.place_sell_order(client, symbol, quantity):
        logger.info(f"Ordem de venda total para {symbol} executada com sucesso.")
        state_manager.adicionar_ativo_cooldown(symbol) # Adiciona ao cooldown
        return True
    else:
        logger.error(f"FALHA ao vender {symbol}. O trade permanecerá ativo para nova tentativa.")
        return False

def _handle_partial_sell(client, trade: dict, pnl: float, current_price: float):
    """
    Executa uma venda parcial.
    Modifica o objeto trade na memória com a nova quantidade e o próximo alvo.
    Retorna o objeto trade modificado e um booleano indicando se a posição foi totalmente fechada.
    """
    symbol = trade['symbol']
    target_index = trade.get('next_target_index', 0)

    sell_percentage = config.TAKE_PROFIT_AMOUNTS[target_index]
    quantity_to_sell = trade['quantity'] * (sell_percentage / 100.0)

    if sell_percentage == 100:
        quantity_to_sell = trade['quantity']

    proporcao_vendida_do_total = quantity_to_sell / trade['initial_quantity']
    pnl_usdt = (pnl / 100) * (config.VALOR_OPERACAO_USDT * proporcao_vendida_do_total)

    logger.info(f"ORDEM DE VENDA PARCIAL para {symbol} (Alvo #{target_index + 1}). PnL: {pnl:.2f}% ({pnl_usdt:+.2f} USDT). Vendendo {quantity_to_sell} unidades.")

    # Novo formato de log
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    reason = f"Take Profit #{target_index + 1}"
    log_msg = (f"[{timestamp}] SELL (Partial) | Symbol: {symbol} | Price: {current_price} | Reason: {reason} | "
               f"PnL: {pnl:+.2f}% ({pnl_usdt:+.2f} USDT) | Qty Sold: {quantity_to_sell}")
    trades_logger.info(log_msg)

    if order_manager.place_sell_order(client, symbol, quantity_to_sell):
        trade['quantity'] -= quantity_to_sell
        trade['next_target_index'] += 1
        logger.info(f"Venda parcial para {symbol} bem-sucedida. Quantidade restante: {trade['quantity']}.")

        is_trade_closed = trade['quantity'] < 1e-9 or sell_percentage == 100
        if is_trade_closed:
             logger.info(f"Trade para {symbol} concluído após a venda final do take profit.")
             state_manager.adicionar_ativo_cooldown(symbol) # Adiciona ao cooldown

        return trade, is_trade_closed
    else:
        logger.error(f"FALHA na venda parcial para {symbol}. O alvo não será atualizado.")
        return trade, False

def check_active_positions(client, active_trades: list):
    """
    Verifica as posições ativas, executa a lógica de venda e, ao final,
    salva o estado atualizado de todos os trades de uma só vez.
    """
    if not active_trades:
        return

    logger.info(f"Iniciando verificação de {len(active_trades)} posições ativas...")
    try:
        tickers = {t['symbol']: float(t['price']) for t in client.get_all_tickers()}
    except Exception as e:
        logger.error(f"Não foi possível obter os preços dos tickers: {e}")
        return

    final_active_trades = []

    for trade in active_trades:
        symbol = trade.get('symbol')
        if not symbol or symbol not in tickers:
            final_active_trades.append(trade)
            continue

        current_price = tickers[symbol]
        entry_price = trade.get('entry_price', 0)
        if entry_price == 0:
            final_active_trades.append(trade)
            continue

        is_trade_still_active = True
        pnl = ((current_price - entry_price) / entry_price) * 100

        trailing_stop_price = trade.get('trailing_stop_price')
        trailing_stop_status = f"{trailing_stop_price:.8f}" if trailing_stop_price else "(inativo)"
        logger.info(
            f" -> Verificando {symbol}: Entrada: {entry_price:.8f}, "
            f"Atual: {current_price:.8f}, PnL: {pnl:+.2f}%. "
            f"Trailing Stop: {trailing_stop_status}"
        )

        # --- 1. Stop Loss Fixo ---
        stop_loss_price = entry_price * (1 - config.STOP_LOSS_PERCENT / 100)
        if current_price <= stop_loss_price:
            if _handle_full_sell(client, trade, "STOP LOSS", pnl, current_price):
                is_trade_still_active = False

        # --- 2. Trailing Stop Loss ---
        if is_trade_still_active:
            activation_price = entry_price * (1 + config.TRAILING_STOP_PERCENT / 100)
            if current_price > activation_price:
                new_stop = current_price * (1 - config.TRAILING_STOP_PERCENT / 100)
                if new_stop > trade.get('trailing_stop_price', 0):
                    trade['trailing_stop_price'] = new_stop

            if 'trailing_stop_price' in trade and current_price <= trade['trailing_stop_price']:
                if _handle_full_sell(client, trade, "TRAILING STOP", pnl, current_price):
                    is_trade_still_active = False

        # --- 3. Take Profit Parcial ---
        if is_trade_still_active:
            target_index = trade.get('next_target_index', 0)
            if target_index < len(config.TAKE_PROFIT_TARGETS):
                target_profit = config.TAKE_PROFIT_TARGETS[target_index]
                if pnl >= target_profit:
                    trade, is_trade_closed = _handle_partial_sell(client, trade, pnl, current_price)
                    if is_trade_closed:
                        is_trade_still_active = False

        if is_trade_still_active:
            final_active_trades.append(trade)

    state_manager.escrever_trades_ativos(final_active_trades)
    logger.info("Verificação de posições ativas concluída. Estado final salvo.")
