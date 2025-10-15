# -*- coding: utf-8 -*-

"""
Módulo Gerenciador de Posições

Responsável por gerenciar os trades que já estão ativos.
Ele verifica as condições de saída (stop, profit, trailing stop) e, no futuro,
executará as ordens de venda.
"""

import state_manager
from logger_setup import logger
# No futuro, importaremos o order_manager aqui

def gerenciar_posicoes_abertas(client):
    """
    Função principal para gerenciar todos os trades ativos.
    """
    trades_ativos = state_manager.ler_trades_ativos()
    if not trades_ativos:
        logger.info("Gerenciador de Posições: Nenhum trade ativo para gerenciar.")
        return

    logger.info(f"Gerenciador de Posições: Verificando {len(trades_ativos)} trades ativos...")

    for trade in trades_ativos:
        symbol = trade['symbol']
        logger.info(f"Verificando {symbol}...")

        try:
            ticker = client.get_symbol_ticker(symbol=symbol)
            preco_atual = float(ticker['price'])

            trailing_stop_price = trade.get('trailing_stop_price')
            if trailing_stop_price and preco_atual < trailing_stop_price:
                logger.info(f"[SIMULAÇÃO] VENDA: {symbol} atingiu o Trailing Stop em {trailing_stop_price}.")
                continue

            take_profit_targets = trade.get('take_profit_targets', [])
            for i, target in enumerate(take_profit_targets):
                if target.get('status') == 'ATIVO' and preco_atual >= target['price']:
                    logger.info(f"[SIMULAÇÃO] VENDA PARCIAL: {symbol} atingiu o alvo {i+1} em {target['price']}.")

            novo_trailing_stop = preco_atual * (1 - (trade.get('stop_loss_percent', 5) / 100))
            if trailing_stop_price is None or novo_trailing_stop > trailing_stop_price:
                 logger.info(f"[SIMULAÇÃO] ATUALIZAÇÃO: Trailing Stop para {symbol} atualizado para {novo_trailing_stop:.8f}.")

        except Exception as e:
            logger.error(f"Erro ao verificar o ativo {symbol}: {e}")

    logger.info("Gerenciador de Posições: Verificação concluída.")