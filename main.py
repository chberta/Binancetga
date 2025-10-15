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

import state_manager
import position_manager
import order_manager
import time
from datetime import datetime, timedelta, timezone

def get_seconds_to_next_candle(timeframe_str: str) -> int:
    """Calcula quantos segundos faltam para o fechamento da próxima vela."""
    # Simplificação: Assume timeframe em horas (ex: '1h', '4h')
    tf_hours = int(timeframe_str.replace('h', ''))
    now = datetime.now(timezone.utc)

    # Encontra o próximo horário de fechamento de vela
    next_candle_time = (now + timedelta(hours=tf_hours)).replace(minute=0, second=0, microsecond=0)

    # Se o horário calculado já passou, adiciona mais um período
    if next_candle_time <= now:
        next_candle_time += timedelta(hours=tf_hours)

    time_to_wait = (next_candle_time - now).total_seconds()
    return int(time_to_wait)

def run_scan_and_open_trades(client, vagas_disponiveis: int):
    """Executa o ciclo de scan e abre novas posições (simulado)."""
    print("\n--- Etapa de Busca por Novos Ativos ---")
    trades_ativos = state_manager.ler_trades_ativos()
    simbolos_ativos = [trade['symbol'] for trade in trades_ativos]

    ativos_filtrados = buscar_e_filtrar_ativos(client)
    ativos_para_analise = [a for a in ativos_filtrados if a not in simbolos_ativos]

    if not ativos_para_analise:
        print("Nenhum novo ativo encontrado para análise.")
        return

    print(f"\n--- Etapa de Análise e Score para {len(ativos_para_analise)} novos ativos ---")
    candidatos_finais = []
    for ativo in ativos_para_analise:
        print(f"\nAnalisando {ativo}...")
        score, df_analise, detalhes = analise_tecnica.calcular_score_ativo(client, ativo)

        print(f"  - Score: {score}")
        if detalhes:
            for key, value in detalhes.items():
                print(f"  - {key}: {value}")

        if score > 0 and analise_tecnica.verificar_sinal_recente(df_analise):
            candidatos_finais.append({'symbol': ativo, 'score': score, 'detalhes': detalhes})
        else:
            print(f"  -> RESULTADO: Descartado.")

    candidatos_ordenados = sorted(candidatos_finais, key=lambda item: item['score'], reverse=True)

    if not candidatos_ordenados:
        print("\nNenhum novo candidato qualificado encontrado nesta rodada.")
        return

    print(f"\n--- Processando {vagas_disponiveis} vagas para novas operações ---")

    for candidato in candidatos_ordenados:
        if vagas_disponiveis <= 0:
            print("Todas as vagas disponíveis foram preenchidas.")
            break

        print(f"\nIniciando processo de abertura de trade para {candidato['symbol']}...")

        # 1. Cria o objeto de trade inicial e salva na memória
        novo_trade = {
            "symbol": candidato['symbol'], "status": "PENDING_BUY", "order_id": None,
            "entry_price": None, "quantity": None, "initial_stop_price": None,
            "trailing_stop_price": None, "take_profit_targets": [],
            "entry_strategy": "Multi-Strategy", "entry_details": candidato['detalhes']
        }
        state_manager.adicionar_trade(novo_trade)
        print(f"  -> Trade para {candidato['symbol']} adicionado à memória com status PENDING_BUY.")

        # 2. Chama o order_manager para executar a compra
        sucesso = order_manager.abrir_novo_trade(client, novo_trade)

        if sucesso:
            print(f"Processo de abertura para {candidato['symbol']} concluído com sucesso.")
            vagas_disponiveis -= 1
        else:
            print(f"Processo de abertura para {candidato['symbol']} falhou.")
            # A lógica de remoção já está no order_manager em caso de falha

def main():
    """
    Função principal que executa o robô em um loop contínuo.
    """
    print("Iniciando o robô de trade para Binance v3.0 (Autônomo)...")
    client = conectar_binance()
    if not client:
        return

    while True:
        print("\n" + "="*50)
        print(f"Iniciando novo ciclo de verificação: {datetime.now().isoformat()}")
        print("="*50)

        # 1. Gerenciar posições abertas
        position_manager.gerenciar_posicoes_abertas(client)

        # 2. Verificar vagas e buscar novas oportunidades
        trades_ativos = state_manager.ler_trades_ativos()
        vagas_disponiveis = config.QUANTIDADE_CRIPTOS_OPERAR - len(trades_ativos)

        print(f"\nMemória: {len(trades_ativos)} trades ativos. Vagas: {vagas_disponiveis}")
        if vagas_disponiveis > 0:
            run_scan_and_open_trades(client, vagas_disponiveis)
        else:
            print("Capacidade máxima de trades atingida. Nenhuma nova busca será feita.")

        # 3. Sincronizar com a próxima vela
        try:
            wait_seconds = get_seconds_to_next_candle(config.TIMEFRAME)
            # Adiciona um pequeno buffer para garantir que a vela fechou
            wait_seconds += 5
            print(f"\nCiclo concluído. Aguardando {wait_seconds // 60} minutos e {wait_seconds % 60} segundos para a próxima vela...")
            time.sleep(wait_seconds)
        except KeyboardInterrupt:
            print("\nRobô interrompido pelo usuário. Desligando...")
            break
        except Exception as e:
            print(f"Ocorreu um erro no loop principal: {e}. Aguardando 5 minutos antes de tentar novamente.")
            time.sleep(300)

if __name__ == "__main__":
    main()