# -*- coding: utf-8 -*-

"""
Gerador de Script Pine para TradingView

Este script lê o arquivo de log de trades (trades.log) e gera um arquivo .pine
para cada símbolo operado. O arquivo .pine pode ser copiado para o Editor Pine
do TradingView para visualizar as entradas e saídas do robô diretamente no gráfico.
"""

import os
from collections import defaultdict
from datetime import datetime

TRADES_LOG_FILE = "data/trades.log"

def gerar_pine_script(symbol, trades):
    """Gera o conteúdo de um script Pine para um único símbolo."""

    # Constrói as strings para preencher os arrays do Pine Script
    buys_data = "\n".join([f'    array.push(time_buys, {buy["timestamp"]})\n    array.push(price_buys, {buy["price"]})\n    array.push(label_buys, "{buy["label"]}")' for buy in trades["buys"]])
    sells_data = "\n".join([f'    array.push(time_sells, {sell["timestamp"]})\n    array.push(price_sells, {sell["price"]})\n    array.push(label_sells, "{sell["label"]}")' for sell in trades["sells"]])

    template = f"""//@version=5
indicator("Sinais do Robô: {symbol}", overlay=true)

// --- DADOS DOS TRADES DE COMPRA ---
var time_buys = array.new_int()
var price_buys = array.new_float()
var label_buys = array.new_string()

// --- DADOS DOS TRADES DE VENDA ---
var time_sells = array.new_int()
var price_sells = array.new_float()
var label_sells = array.new_string()

// Preenche os arrays de compra
if (bar_index == 0) {{
{buys_data}
}}

// Preenche os arrays de venda
if (bar_index == 0) {{
{sells_data}
}}

// Desenha as compras no gráfico
for i = 0 to array.size(time_buys) - 1
    if (time == array.get(time_buys, i))
        label.new(time, array.get(price_buys, i), array.get(label_buys, i),
                  style=label.style_label_up, color=color.new(color.green, 20), textcolor=color.white)

// Desenha as vendas no gráfico
for i = 0 to array.size(time_sells) - 1
    if (time == array.get(time_sells, i))
        label.new(time, array.get(price_sells, i), array.get(label_sells, i),
                  style=label.style_label_down, color=color.new(color.red, 20), textcolor=color.white)
"""
    return template


def main():
    """
    Função principal que orquestra a leitura do log e a geração dos scripts.
    """
    print("Iniciando o Gerador de Script Pine para TradingView...")

    if not os.path.exists(TRADES_LOG_FILE):
        print(f"Arquivo de log '{TRADES_LOG_FILE}' não encontrado.")
        return

    trades_por_symbol = defaultdict(lambda: {"buys": [], "sells": []})

    with open(TRADES_LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                # Normaliza e divide a linha do log
                parts = [p.strip() for p in line.strip().split('|')]
                if len(parts) < 4: continue

                timestamp_str = parts[0].replace('[', '').replace(']', '')
                timestamp_dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                timestamp_ms = int(timestamp_dt.timestamp() * 1000)

                trade_type_full = parts[1]
                symbol = parts[2].split(':')[1].strip()
                price = float(parts[3].split(':')[1].strip())

                trade_info = { "timestamp": timestamp_ms, "price": price }

                if "BUY" in trade_type_full:
                    trade_info["label"] = "Compra"
                    trades_por_symbol[symbol]["buys"].append(trade_info)

                elif "SELL" in trade_type_full:
                    # Garante que a linha de log de venda tenha partes suficientes
                    if len(parts) < 6: continue
                    reason = parts[4].split(':')[1].strip()
                    pnl_info = parts[5].split(':')[1].strip()
                    trade_info["label"] = f"{reason}\\n{pnl_info}"
                    trades_por_symbol[symbol]["sells"].append(trade_info)

            except (IndexError, ValueError) as e:
                print(f"Linha de log ignorada devido a erro de parsing: '{line.strip()}' | Erro: {e}")
                continue

    if not trades_por_symbol:
        print("Nenhum trade encontrado no arquivo de log.")
        print("Geração de scripts concluída.")
        return

    output_dir = "pine_scripts"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for symbol, trades in trades_por_symbol.items():
        pine_script_content = gerar_pine_script(symbol, trades)
        file_path = os.path.join(output_dir, f"{symbol}_trades.pine")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(pine_script_content)
        print(f"Script gerado para {symbol} em: {file_path}")

    print(f"\nEncontrados e processados trades para {len(trades_por_symbol)} símbolos.")
    print("Geração de scripts concluída.")


if __name__ == "__main__":
    main()
