# -*- coding: utf-8 -*-

"""
Script de Teste para o Scan por Volume

Este script executa apenas a função de descoberta por volume e imprime
os 100 principais ativos encontrados na Binance, para fins de validação e depuração.
"""

import main
import discovery

def run_test():
    """
    Executa o teste de scan por volume.
    """
    print("--- Iniciando Teste de Scan por Volume ---")

    client = main.conectar_binance()
    if not client:
        print("Falha ao conectar. Encerrando teste.")
        return

    try:
        # Pega a lista de todos os símbolos negociáveis primeiro
        tradable_symbols = discovery.get_tradable_spot_symbols(client)

        # Em seguida, busca o ranking de volume para esses símbolos
        top_volume_list = discovery.discover_top_by_volume(client, tradable_symbols)

        if top_volume_list:
            print("\n--- Top 100 Ativos por Volume (24h) ---")
            for i, symbol in enumerate(top_volume_list[:100]):
                print(f"{i+1:3d}. {symbol}")
            print("\n--- Fim do Teste ---")
        else:
            print("Nenhum ativo encontrado na busca por volume.")

    except Exception as e:
        print(f"\nOcorreu um erro durante o teste: {e}")

if __name__ == "__main__":
    run_test()