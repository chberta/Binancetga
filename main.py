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
    Busca e filtra ativos usando get_exchange_info() para mais segurança e precisão.
    """
    try:
        print("Buscando informações de todos os ativos na Binance...")
        exchange_info = client.get_exchange_info()
        symbols_data = exchange_info['symbols']

        # 1. Filtro de Qualidade: Apenas ativos SPOT, com status TRADING e par USDT
        print("Filtrando por ativos de qualidade (SPOT, TRADING, par USDT)...")
        ativos_spot_usdt = []
        for s in symbols_data:
            if 'SPOT' in s['permissions'] and s['status'] == 'TRADING' and s['symbol'].endswith('USDT'):
                ativos_spot_usdt.append(s['symbol'])

        print(f"Encontrados {len(ativos_spot_usdt)} ativos SPOT com par USDT em negociação.")

        # 2. Aplicar a Lista Negra pessoal do usuário
        print("Aplicando a lista negra pessoal...")
        ativos_sem_lista_negra = [s for s in ativos_spot_usdt if s not in config.LISTA_NEGRA]

        # 3. Filtrar pelo Top N de Volume (usando get_ticker para dados de 24h)
        print("Buscando dados de volume e selecionando o Top N...")
        all_tickers = client.get_ticker()
        df_tickers = pd.DataFrame(all_tickers)
        df_tickers = df_tickers[df_tickers['symbol'].isin(ativos_sem_lista_negra)]

        df_tickers.loc[:, 'volume'] = df_tickers['volume'].astype(float)
        top_volume_pairs = df_tickers.sort_values(by='volume', ascending=False).head(config.MAX_TOP_VOLUME)

        # 4. Verificar a idade do gráfico para os ativos do Top N
        print(f"Verificando a idade do gráfico para os {len(top_volume_pairs)} principais ativos...")
        limite_antiguidade = datetime.now() - timedelta(weeks=52)
        ativos_finais = []

        for symbol in top_volume_pairs['symbol']:
            klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1WEEK, limit=1)
            if klines:
                data_primeiro_candle = datetime.fromtimestamp(klines[0][0] / 1000)
                if data_primeiro_candle < limite_antiguidade:
                    ativos_finais.append(symbol)

        print(f"Encontrados {len(ativos_finais)} ativos que atendem a TODOS os critérios (Qualidade, Volume e Idade).")

        return ativos_finais

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