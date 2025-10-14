# -*- coding: utf-8 -*-

import config
from binance.client import Client
import json

def main():
    """
    Sonda de diagnóstico para obter informações de um símbolo específico.
    """
    print("Iniciando a sonda de diagnóstico...")

    try:
        client = Client(config.API_KEY, config.API_SECRET)
        print("Conexão com a Binance bem-sucedida.")

        symbol_info = client.get_symbol_info('BTCUSDT')

        if symbol_info:
            print("\n--- INFORMAÇÕES DO SÍMBOLO: BTCUSDT ---")
            # Usamos json.dumps para formatar a saída de forma legível
            print(json.dumps(symbol_info, indent=4))
            print("\n--- FIM DAS INFORMAÇÕES ---")
        else:
            print("Não foi possível obter informações para o símbolo BTCUSDT.")

    except Exception as e:
        print(f"\nOcorreu um erro: {e}")

if __name__ == "__main__":
    main()