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
            logger.info("Conexão com a Binance bem-sucedida!")
            return client
        else:
            logger.error(f"Erro ao conectar com a Binance. Status: {status['msg']}")
            return None
    except Exception as e:
        logger.error(f"Ocorreu um erro ao conectar com a API da Binance: {e}")
        return None

import discovery

def _rank_map(lst: list) -> dict:
    return {sym: i + 1 for i, sym in enumerate(lst)}

def combine_symbol_lists(vol_list: list, cap_list: list, mode: str) -> list:
    """Combina as listas de Volume e Market Cap com base no modo escolhido."""
    r_vol, r_cap = _rank_map(vol_list), _rank_map(cap_list)

    if mode == "intersect":
        commons = [s for s in vol_list if s in r_cap]
        commons.sort(key=lambda s: (r_vol.get(s, 0) + r_cap.get(s, 0)) / 2.0)
        return commons

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
        tradable_symbols = discovery.get_tradable_spot_symbols(client)

        vol_list = discovery.discover_top_by_volume(client, tradable_symbols)
        cap_list = discovery.discover_top_by_marketcap(tradable_symbols)

        logger.info(f"Combinando as listas de Volume e Market Cap...")
        # Combina as listas completas primeiro
        combined_list = combine_symbol_lists(
            vol_list[:config.TOP_N_VOLUME],
            cap_list[:config.TOP_N_MCAP],
            9999, # Pega uma lista grande para filtrar depois
            config.COMBINE_MODE
        )

        logger.info(f"Aplicando filtros de idade e lista negra a {len(combined_list)} candidatos...")
        limite_antiguidade = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(weeks=52)

        ativos_filtrados_por_idade = []
        start_ts = int(datetime(2017, 1, 1).timestamp() * 1000)
        for symbol in combined_list:
            if symbol in config.LISTA_NEGRA:
                continue

            try:
                # A forma correta de pegar a primeira vela
                klines = client.get_klines(
                    symbol=symbol,
                    interval=Client.KLINE_INTERVAL_1WEEK,
                    startTime=start_ts,
                    limit=1
                )
                if klines:
                    data_primeiro_candle = datetime.fromtimestamp(klines[0][0] / 1000)
                    if data_primeiro_candle < limite_antiguidade:
                        ativos_filtrados_por_idade.append(symbol)
            except Exception as e:
                logger.warning(f"Não foi possível verificar a idade de {symbol}: {e}")


        # Só agora pega o Top N final
        ativos_finais = ativos_filtrados_por_idade[:config.TOP_N_FINAL]
        logger.info(f"Encontrados {len(ativos_finais)} ativos que atendem a TODOS os critérios e foram selecionados para análise.")

        return ativos_finais

    except Exception as e:
        logger.error(f"Ocorreu um erro ao buscar e filtrar ativos: {e}", exc_info=True)
        return []

import time
from datetime import datetime, timedelta, timezone
from logger_setup import logger

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

def run_scan(client):
    """Executa o ciclo de scan e análise."""
    logger.info("--- Iniciando Etapa de Busca por Novos Ativos ---")

    ativos_filtrados = buscar_e_filtrar_ativos(client)

    if not ativos_filtrados:
        logger.info("Nenhum ativo passou em todos os filtros. Encerrando.")
        return

    logger.info(f"--- Iniciando Etapa de Análise e Score para {len(ativos_filtrados)} ativos ---")
    candidatos_finais = []
    for ativo in ativos_filtrados:
        logger.info(f"Analisando {ativo}...")
        score, df_analise, detalhes = analise_tecnica.calcular_score_ativo(client, ativo)

        log_detalhes = f"Score: {score} | Detalhes: {detalhes}"
        logger.debug(log_detalhes)

        if score > 0 and analise_tecnica.verificar_sinal_recente(df_analise):
            candidatos_finais.append({'symbol': ativo, 'score': score})
        else:
            logger.info(f" -> {ativo} descartado (score baixo ou sinal antigo).")

    candidatos_ordenados = sorted(candidatos_finais, key=lambda item: item['score'], reverse=True)

    if not candidatos_ordenados:
        logger.info("Nenhum candidato qualificado encontrado nesta rodada.")
        return

    logger.info(f"--- Top {config.QUANTIDADE_CRIPTOS_OPERAR} Candidatos Encontrados ---")
    for candidato in candidatos_ordenados[:config.QUANTIDADE_CRIPTOS_OPERAR]:
        logger.info(f"  - {candidato['symbol']} (Score: {candidato['score']})")

def main():
    """
    Função principal que executa o robô.
    """
    logger.info("Iniciando o robô de trade para Binance...")
    client = conectar_binance()
    if not client:
        return

    logger.info("="*50)
    logger.info(f"Iniciando ciclo de verificação: {datetime.now().isoformat()}")
    logger.info("="*50)

    run_scan(client)

    logger.info("Ciclo de análise concluído.")

if __name__ == "__main__":
    main()