# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

import config
import pandas as pd
from binance.client import Client
from datetime import datetime, timedelta

def conectar_binance():
    """
    Cria e retorna um cliente da API da Binance.
    """
    try:
        client = Client(config.API_KEY, config.API_SECRET)
        status = client.get_system_status()
        if status['status'] == 0:
            print("Conexão com a Binance bem-sucedida!")
            return client
        else:
            print(f"Erro ao conectar com a Binance. Status: {status['msg']}")
            return None
    except Exception as e:
        print(f"Ocorreu um erro ao conectar com a API da Binance: {e}")
        return None

def buscar_e_filtrar_ativos(client):
    """
    Busca, filtra e ordena os ativos da Binance de acordo com os critérios.
    """
    try:
        # 1. Buscar todos os tickers de 24h
        print("Buscando todos os ativos na Binance...")
        all_tickers = client.get_ticker()
        df_tickers = pd.DataFrame(all_tickers)

        # 2. Filtrar pares que terminam com USDT e não são de alavancagem/down
        print("Filtrando pares USDT...")
        usdt_pairs = df_tickers[df_tickers['symbol'].str.endswith('USDT')]
        usdt_pairs = usdt_pairs[~usdt_pairs['symbol'].isin(config.LISTA_NEGRA)]

        # 3. Filtrar por tempo de listagem (mais de 52 semanas)
        # NOTA: Esta abordagem faz uma chamada de API por ativo e pode ser lenta.
        # Para uma solução mais otimizada, considere criar um cache local
        # com as datas de listagem dos ativos para evitar chamadas repetidas.
        print("Filtrando por tempo de listagem (ativos com mais de 52 semanas)...")
        limite_antiguidade = datetime.now() - timedelta(weeks=52)
        ativos_antigos = []

        for symbol in usdt_pairs['symbol']:
            # Pega o primeiro candle disponível (o mais antigo)
            klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_WEEKLY, limit=1)
            if klines:
                timestamp_primeiro_candle = klines[0][0] / 1000  # Converte ms para s
                data_primeiro_candle = datetime.fromtimestamp(timestamp_primeiro_candle)

                if data_primeiro_candle < limite_antiguidade:
                    ativos_antigos.append(symbol)

        print(f"Encontrados {len(ativos_antigos)} ativos com mais de 52 semanas.")
        usdt_pairs = usdt_pairs[usdt_pairs['symbol'].isin(ativos_antigos)]

        # 4. Ordenar por volume de negociação
        print("Ordenando ativos por volume de negociação...")
        usdt_pairs['volume'] = usdt_pairs['volume'].astype(float)
        usdt_pairs_sorted = usdt_pairs.sort_values(by='volume', ascending=False)

        return usdt_pairs_sorted['symbol'].tolist()

    except Exception as e:
        print(f"Ocorreu um erro ao buscar e filtrar ativos: {e}")
        return []

import analise_tecnica

def main():
    """
    Função principal para executar o robô de trade.
    """
    print("Iniciando o robô de trade para Binance...")
    client = conectar_binance()

    if client:
        print("\n--- Etapa de Filtragem de Ativos ---")
        ativos_filtrados = buscar_e_filtrar_ativos(client)

        if not ativos_filtrados:
            print("Nenhum ativo encontrado que corresponda aos critérios de filtragem. Encerrando.")
            return

        print(f"\n--- Etapa de Análise e Score para os {len(ativos_filtrados)} ativos filtrados ---")
        candidatos_finais = {}
        for ativo in ativos_filtrados:
            print(f"Analisando {ativo}...")
            score, df_analise = analise_tecnica.calcular_score_ativo(client, ativo)

            if score > 0:
                # Agora, verificamos se o sinal é recente
                if analise_tecnica.verificar_sinal_recente(df_analise):
                    print(f"  -> {ativo} tem sinal recente. Score: {score}")
                    candidatos_finais[ativo] = score
                else:
                    print(f"  -> {ativo} com score {score}, mas sinal não é recente. Descartado.")

        # Ordenar os candidatos finais pelo score
        ativos_prontos_para_operar = sorted(candidatos_finais.items(), key=lambda item: item[1], reverse=True)

        if ativos_prontos_para_operar:
            print(f"\n--- Top {config.QUANTIDADE_CRIPTOS_OPERAR} Ativos Prontos para Operar ---")
            for ativo, score in ativos_prontos_para_operar[:config.QUANTIDADE_CRIPTOS_OPERAR]:
                print(f"- {ativo} (Score: {score}) - SINAL RECENTE CONFIRMADO")
        else:
            print("\nNenhum ativo com score positivo e sinal recente foi encontrado.")

if __name__ == "__main__":
    main()