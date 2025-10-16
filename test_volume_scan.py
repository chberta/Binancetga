# -*- coding: utf-8 -*-

"""
Script de Teste para o Scan por Volume

Este script executa apenas a função de descoberta por volume e imprime
os 100 principais ativos encontrados na Binance, para fins de validação e depuração.
"""

import main
import discovery
import config
from datetime import datetime, timedelta
from binance.client import Client

def run_test():
    """
    Executa o teste de scan por volume com filtragem detalhada.
    """
    print("--- Iniciando Teste de Scan e Filtros ---")

    client = main.conectar_binance()
    if not client:
        print("Falha ao conectar. Encerrando teste.")
        return

    try:
        tradable_symbols = discovery.get_tradable_spot_symbols(client)
        top_volume_list = discovery.discover_top_by_volume(client, tradable_symbols)

        if not top_volume_list:
            print("Nenhum ativo encontrado na busca por volume.")
            return

        print("\n--- Verificando Top 100 Ativos por Volume ---")

        limite_antiguidade = datetime.now() - timedelta(weeks=52)
        ativos_aprovados = []

        for i, symbol in enumerate(top_volume_list[:100]):
            print(f"\n{i+1}. Verificando {symbol}...")

            # Filtro 1: Lista Negra
            if symbol in config.LISTA_NEGRA:
                print(f"   --> RESULTADO: DESCARTADO (Motivo: Lista Negra)")
                continue
            else:
                print(f"   - Na Lista Negra? Não.")

            # Filtro 2: Idade do Gráfico
            try:
                # A forma correta de pegar a primeira vela é sem 'limit' e com um startTime antigo.
                klines = client.get_klines(symbol=symbol, interval='1w', startTime="2017-01-01")
                if klines:
                    data_primeiro_candle = datetime.fromtimestamp(klines[0][0] / 1000)
                    if data_primeiro_candle < limite_antiguidade:
                        print(f"   - Idade do Gráfico: OK (Primeira vela em {data_primeiro_candle.date()})")
                        print(f"   --> RESULTADO: APROVADO")
                        ativos_aprovados.append(symbol)
                    else:
                        print(f"   - Idade do Gráfico: REPROVADO (Primeira vela em {data_primeiro_candle.date()})")
                        print(f"   --> RESULTADO: DESCARTADO (Motivo: Idade do Gráfico)")
                else:
                    print(f"   - Idade do Gráfico: REPROVADO (Não foi possível obter o histórico)")
                    print(f"   --> RESULTADO: DESCARTADO (Motivo: Sem Histórico)")
            except Exception as e:
                print(f"   - Erro ao verificar idade para {symbol}: {e}")
                print(f"   --> RESULTADO: DESCARTADO (Motivo: Erro na API)")

        print("\n" + "="*50)
        print("--- Lista Final de Ativos Aprovados ---")
        if ativos_aprovados:
            for i, symbol in enumerate(ativos_aprovados):
                print(f"{i+1:3d}. {symbol}")
        else:
            print("(Nenhum ativo aprovado)")
        print("="*50)

    except Exception as e:
        print(f"\nOcorreu um erro geral durante o teste: {e}")

if __name__ == "__main__":
    run_test()