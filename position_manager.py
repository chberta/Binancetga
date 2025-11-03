# -*- coding: utf-8 -*-

"""
Módulo Position Manager

Gerencia posições abertas, verificando preços e decidindo vendas com base
nas estratégias de Stop Loss, Trailing Stop e Take Profit Parcial.
"""

import config
import state_manager
import order_manager
from logger_setup import logger

def _handle_full_sell(client, trade: dict, reason: str, pnl: float):
    """Vende 100% da posição restante e a remove da memória."""
    symbol = trade['symbol']
    quantity = trade['quantity']
    logger.info(f"ORDEM DE VENDA TOTAL para {symbol}. Motivo: {reason}. PnL: {pnl:.2f}%.")

    if order_manager.place_sell_order(client, symbol, quantity):
        state_manager.remover_trade(symbol)
        logger.info(f"Trade para {symbol} fechado e removido da memória.")
        return True
    else:
        logger.error(f"FALHA ao vender {symbol}. O trade permanecerá ativo.")
        return False

def _handle_partial_sell(client, trade: dict, pnl: float):
    """Executa uma venda parcial baseada nos alvos de Take Profit."""
    symbol = trade['symbol']
    target_index = trade.get('next_target_index', 0)

    # Calcula a quantidade a ser vendida
    sell_percentage = config.TAKE_PROFIT_AMOUNTS[target_index]
    initial_quantity = trade['initial_quantity']
    quantity_to_sell = initial_quantity * (sell_percentage / 100.0)

    # Ajuste para o último alvo, garantindo que vende tudo o que sobrou
    if sell_percentage == 100:
        quantity_to_sell = trade['quantity']

    logger.info(f"ORDEM DE VENDA PARCIAL para {symbol} (Alvo #{target_index + 1}). PnL: {pnl:.2f}%. Vendendo {quantity_to_sell} unidades.")

    if order_manager.place_sell_order(client, symbol, quantity_to_sell):
        trade['quantity'] -= quantity_to_sell
        trade['next_target_index'] += 1
        logger.info(f"Venda parcial para {symbol} bem-sucedida. Quantidade restante: {trade['quantity']}.")

        if trade['quantity'] < 1e-9 or sell_percentage == 100:
            state_manager.remover_trade(symbol)
            logger.info(f"Trade para {symbol} concluído após a venda final.")
        else:
            # Salva o estado atualizado do trade imediatamente após a venda parcial
            trades = state_manager.ler_trades_ativos()
            for i, t in enumerate(trades):
                if t['symbol'] == symbol:
                    trades[i] = trade
                    break
            state_manager.escrever_trades_ativos(trades)
        return True
    else:
        logger.error(f"FALHA na venda parcial para {symbol}. O alvo não será atualizado.")
        return False

def check_active_positions(client, active_trades: list):
    """Verifica as posições ativas e executa a lógica de venda."""
    if not active_trades: return

    logger.info(f"Iniciando verificação de {len(active_trades)} posições ativas...")
    try:
        tickers = {t['symbol']: float(t['price']) for t in client.get_all_tickers()}
    except Exception as e:
        logger.error(f"Não foi possível obter os preços dos tickers: {e}")
        return

    trades_to_update = []
    for trade in active_trades:
        symbol = trade.get('symbol')
        if not symbol or symbol not in tickers: continue

        current_price = tickers[symbol]
        entry_price = trade.get('entry_price', 0)
        if entry_price == 0: continue

        pnl = ((current_price - entry_price) / entry_price) * 100

        # --- 1. Stop Loss Fixo ---
        stop_loss_price = entry_price * (1 - config.STOP_LOSS_PERCENT / 100)
        if current_price <= stop_loss_price:
            _handle_full_sell(client, trade, "STOP LOSS", pnl)
            continue

        # --- 2. Trailing Stop Loss ---
        activation_price = entry_price * (1 + config.TRAILING_STOP_PERCENT / 100)
        if current_price > activation_price:
            new_stop = current_price * (1 - config.TRAILING_STOP_PERCENT / 100)
            if new_stop > trade.get('trailing_stop_price', 0):
                trade['trailing_stop_price'] = new_stop

        if 'trailing_stop_price' in trade and current_price <= trade['trailing_stop_price']:
            _handle_full_sell(client, trade, "TRAILING STOP", pnl)
            continue

        # --- 3. Take Profit Parcial ---
        target_index = trade.get('next_target_index', 0)
        if target_index < len(config.TAKE_PROFIT_TARGETS):
            target_profit = config.TAKE_PROFIT_TARGETS[target_index]
            if pnl >= target_profit:
                _handle_partial_sell(client, trade, pnl)

        trades_to_update.append(trade)

    # A lógica de salvar o estado agora é tratada dentro das funções de venda para maior robustez.
    # Apenas o `trailing_stop_price` atualizado precisa ser salvo no final do ciclo.
    current_trades = state_manager.ler_trades_ativos()
    for trade in current_trades:
        for updated_trade in trades_to_update:
            if trade['symbol'] == updated_trade['symbol'] and 'trailing_stop_price' in updated_trade:
                trade['trailing_stop_price'] = updated_trade['trailing_stop_price']

    state_manager.escrever_trades_ativos(current_trades)
    logger.info("Verificação de posições ativas concluída.")
