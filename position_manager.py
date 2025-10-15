# -*- coding: utf-8 -*-

"""
Módulo Gerenciador de Posições

Responsável por gerenciar os trades que já estão ativos.
Ele verifica as condições de saída (stop, profit, trailing stop) e, no futuro,
executará as ordens de venda.
"""

import state_manager
# No futuro, importaremos o order_manager aqui

def gerenciar_posicoes_abertas(client):
    """
    Função principal para gerenciar todos os trades ativos.
    """
    trades_ativos = state_manager.ler_trades_ativos()
    if not trades_ativos:
        print("Gerenciador de Posições: Nenhum trade ativo para gerenciar.")
        return

    print(f"Gerenciador de Posições: Verificando {len(trades_ativos)} trades ativos...")

    for trade in trades_ativos:
        symbol = trade['symbol']
        print(f"  -> Verificando {symbol}...")

        try:
            # Busca o preço atual do ativo
            ticker = client.get_symbol_ticker(symbol=symbol)
            preco_atual = float(ticker['price'])

            # Lógica de Trailing Stop (simulação)
            trailing_stop_price = trade.get('trailing_stop_price')
            if trailing_stop_price and preco_atual < trailing_stop_price:
                print(f"    [SIMULAÇÃO] VENDA: {symbol} atingiu o Trailing Stop em {trailing_stop_price}.")
                # No futuro: order_manager.fechar_trade(trade)
                # state_manager.remover_trade(symbol)
                # history_manager.registrar_trade(...)
                continue # Pula para o próximo trade, pois este seria fechado

            # Lógica de Take Profit (simulação)
            take_profit_targets = trade.get('take_profit_targets', [])
            for i, target in enumerate(take_profit_targets):
                if target.get('status') == 'ATIVO' and preco_atual >= target['price']:
                    print(f"    [SIMULAÇÃO] VENDA PARCIAL: {symbol} atingiu o alvo {i+1} em {target['price']}.")
                    # No futuro: order_manager.executar_venda_parcial(trade, target)
                    # O status do alvo seria atualizado para 'CONCLUIDO'

            # Lógica de atualização do Trailing Stop (simulação)
            # Se o preço subir, o trailing stop sobe junto.
            # Esta é uma lógica simples, pode ser refinada com ATR, etc.
            novo_trailing_stop = preco_atual * (1 - (trade.get('stop_loss_percent', 5) / 100))
            if trailing_stop_price is None or novo_trailing_stop > trailing_stop_price:
                 print(f"    [SIMULAÇÃO] ATUALIZAÇÃO: Trailing Stop para {symbol} atualizado para {novo_trailing_stop:.8f}.")
                 # No futuro: o novo valor seria salvo no state_manager

        except Exception as e:
            print(f"    Erro ao verificar o ativo {symbol}: {e}")

    print("Gerenciador de Posições: Verificação concluída.")