# -*- coding: utf-8 -*-

import config
import pandas as pd
from binance.client import Client
from datetime import datetime, timedelta
import analise_tecnica

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

import discovery

def _rank_map(lst: list) -> dict:
    return {sym: i + 1 for i, sym in enumerate(lst)}

def combine_symbol_lists(vol_list: list, cap_list: list, top_n: int, mode: str) -> list:
    """Combina as listas de Volume e Market Cap com base no modo escolhido."""
    r_vol, r_cap = _rank_map(vol_list), _rank_map(cap_list)

    if mode == "intersect":
        commons = [s for s in vol_list if s in r_cap]
        commons.sort(key=lambda s: (r_vol.get(s, 0) + r_cap.get(s, 0)) / 2.0)
        return commons[:top_n]

    universe = list(dict.fromkeys(vol_list + cap_list))
    max_penalty = len(universe) * 2

    scored = []
    for s in universe:
        rv = r_vol.get(s, max_penalty)
        rc = r_cap.get(s, max_penalty)
        if mode == "union":
            is_common = 1 if (s in r_vol and s in r_cap) else 0
            score = (rv + rc) / 2.0
            scored.append((-is_common, score, s)) # Prioriza comuns
        else: # blend
            score = rv + rc
            scored.append((score, s))

    scored.sort()

    final_list = [s for *_, s in scored]
    return final_list[:top_n]

def buscar_e_filtrar_ativos(client):
    """
    Orquestra o processo de descoberta e filtragem v2.0.
    """
    try:
        # 1. Descoberta de Ativos
        vol_list = discovery.discover_top_by_volume(client)[:config.TOP_N_VOLUME]
        cap_list = discovery.discover_top_by_marketcap(client)[:config.TOP_N_MCAP]

        # 2. Combinação Inteligente
        print(f"Combinando as listas usando o modo '{config.COMBINE_MODE}'...")
        combined_list = combine_symbol_lists(vol_list, cap_list, config.TOP_N_FINAL, config.COMBINE_MODE)

        # 3. Aplicar a Lista Negra pessoal do usuário
        print("Aplicando a lista negra pessoal...")
        ativos_sem_lista_negra = [s for s in combined_list if s not in config.LISTA_NEGRA]

        # 4. Verificar a idade do gráfico para a lista final
        print(f"Verificando a idade do gráfico para os {len(ativos_sem_lista_negra)} principais ativos...")
        limite_antiguidade = datetime.now() - timedelta(weeks=52)
        ativos_finais = []

        for symbol in ativos_sem_lista_negra:
            klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1WEEK, limit=1)
            if klines:
                data_primeiro_candle = datetime.fromtimestamp(klines[0][0] / 1000)
                if data_primeiro_candle < limite_antiguidade:
                    ativos_finais.append(symbol)

        print(f"Encontrados {len(ativos_finais)} ativos que atendem a TODOS os critérios.")

        return ativos_finais

    except Exception as e:
        print(f"Ocorreu um erro ao buscar e filtrar ativos: {e}")
        return []

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

            print(f"  - Score: {score}")
            if detalhes:
                for key, value in detalhes.items():
                    print(f"  - {key}: {value}")
            else:
                print("  - Detalhes: Não foi possível calcular os indicadores (dados insuficientes).")

            if score > 0:
                if analise_tecnica.verificar_sinal_recente(df_analise):
                    print(f"  -> RESULTADO: {ativo} tem sinal RECENTE. Adicionado à lista de candidatos.")
                    candidatos_finais[ativo] = score
                else:
                    print(f"  -> RESULTADO: {ativo} com score positivo, mas sinal NÃO é recente. Descartado.")
            else:
                print(f"  -> RESULTADO: Score baixo. Descartado.")

        ativos_prontos_para_operar = sorted(candidatos_finais.items(), key=lambda item: item[1], reverse=True)

        if ativos_prontos_para_operar:
            print(f"\n--- Top {config.QUANTIDADE_CRIPTOS_OPERAR} Ativos Prontos para Operar ---")
            for ativo, score in ativos_prontos_para_operar[:config.QUANTIDADE_CRIPTOS_OPERAR]:
                print(f"- {ativo} (Score: {score}) - SINAL RECENTE CONFIRMADO")
        else:
            print("\nNenhum ativo com score positivo e sinal recente foi encontrado.")

if __name__ == "__main__":
    main()