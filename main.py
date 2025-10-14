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
    Busca, filtra e ordena os ativos da Binance de acordo com a nova lógica eficiente.
    """
    try:
        # 1. Buscar todos os tickers e filtrar por USDT e lista negra
        print("Buscando e filtrando pares USDT...")
        all_tickers = client.get_ticker()
        df_tickers = pd.DataFrame(all_tickers)

        usdt_pairs = df_tickers[df_tickers['symbol'].str.endswith('USDT')]
        usdt_pairs = usdt_pairs[~usdt_pairs['symbol'].isin(config.LISTA_NEGRA)]

        # 2. Ordenar por volume e selecionar o Top N
        print(f"Selecionando os {config.MAX_TOP_VOLUME} ativos com maior volume...")
        usdt_pairs.loc[:, 'volume'] = usdt_pairs['volume'].astype(float)
        top_volume_pairs = usdt_pairs.sort_values(by='volume', ascending=False).head(config.MAX_TOP_VOLUME)

        # 3. Filtrar o Top N por tempo de listagem (mais de 52 semanas)
        print(f"Verificando a idade dos {config.MAX_TOP_VOLUME} principais ativos...")
        limite_antiguidade = datetime.now() - timedelta(weeks=52)
        ativos_antigos_e_com_volume = []

        for symbol in top_volume_pairs['symbol']:
            # Pega o primeiro candle disponível (o mais antigo)
            klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1WEEK, limit=1)
            if klines:
                timestamp_primeiro_candle = klines[0][0] / 1000  # Converte ms para s
                data_primeiro_candle = datetime.fromtimestamp(timestamp_primeiro_candle)

                if data_primeiro_candle < limite_antiguidade:
                    ativos_antigos_e_com_volume.append(symbol)

        print(f"Encontrados {len(ativos_antigos_e_com_volume)} ativos que atendem a todos os critérios.")

        # A lista já está ordenada por volume, então podemos retorná-la diretamente
        return ativos_antigos_e_com_volume

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
            print(f"\nAnalisando {ativo}...")
            score, df_analise, detalhes = analise_tecnica.calcular_score_ativo(client, ativo)

            # Imprime o log detalhado
            print(f"  - Score: {score}")
            if detalhes:
                for key, value in detalhes.items():
                    print(f"  - {key}: {value}")
            else:
                print("  - Detalhes: Não foi possível calcular os indicadores (dados insuficientes).")

            if score > 0:
                # Agora, verificamos se o sinal é recente
                if analise_tecnica.verificar_sinal_recente(df_analise):
                    print(f"  -> RESULTADO: {ativo} tem sinal RECENTE. Adicionado à lista de candidatos.")
                    candidatos_finais[ativo] = score
                else:
                    print(f"  -> RESULTADO: {ativo} com score positivo, mas sinal NÃO é recente. Descartado.")
            else:
                print(f"  -> RESULTADO: Score baixo. Descartado.")

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