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

def combine_symbol_lists(vol_list: list, cap_list: list, top_n: int, mode: str) -> list:
    """Combina as listas de Volume e Market Cap com base no modo escolhido."""
    r_vol, r_cap = _rank_map(vol_list), _rank_map(cap_list)

    if mode == "intersect":
        commons = [s for s in vol_list if s in r_cap]
        # Ordena os comuns pela média de seus ranks
        commons.sort(key=lambda s: (r_vol.get(s, 0) + r_cap.get(s, 0)) / 2.0)
        return commons[:top_n]

    # Para 'union' e 'blend', processamos o universo completo
    universe = list(dict.fromkeys(vol_list + cap_list))
    max_penalty = len(universe) * 2

    scored = []
    for s in universe:
        rv = r_vol.get(s, max_penalty)
        rc = r_cap.get(s, max_penalty)

        if mode == "union":
            # Para 'union', priorizamos os que estão em ambas as listas
            is_common = 1 if (s in r_vol and s in r_cap) else 0
            score = (rv + rc) / 2.0  # Média dos ranks
            scored.append((-is_common, score, s))  # '-is_common' para ordenar comuns primeiro
        else:  # 'blend'
            # Para 'blend', simplesmente somamos os ranks
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
        combined_list = combine_symbol_lists(
            vol_list[:config.TOP_N_VOLUME],
            cap_list[:config.TOP_N_MCAP],
            9999, # Pega uma lista grande para filtrar depois
            config.COMBINE_MODE
        )

        logger.info(f"Aplicando filtros de idade e lista negra a {len(combined_list)} candidatos...")
        limite_antiguidade = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(weeks=52)

        # Converte a data de início para um timestamp em milissegundos, como exigido pela API
        start_ts = int(datetime(2017, 1, 1).timestamp() * 1000)

        ativos_filtrados = []
        for symbol in combined_list:
            if symbol in config.LISTA_NEGRA:
                continue

            try:
                # Usa o timestamp em milissegundos para o parâmetro startTime
                klines = client.get_klines(symbol=symbol, interval='1w', startTime=start_ts)
                if klines:
                    data_primeiro_candle = datetime.fromtimestamp(klines[0][0] / 1000)
                    if data_primeiro_candle < limite_antiguidade:
                        ativos_filtrados.append(symbol)
            except Exception as e:
                logger.warning(f"Não foi possível verificar a idade de {symbol}: {e}")


        ativos_finais = ativos_filtrados[:config.TOP_N_FINAL]
        logger.info(f"Encontrados {len(ativos_finais)} ativos que atendem a TODOS os critérios e foram selecionados para análise.")

        return ativos_finais

    except Exception as e:
        logger.error(f"Ocorreu um erro ao buscar e filtrar ativos: {e}", exc_info=True)
        return []

import time
from datetime import datetime, timedelta, timezone
from logger_setup import logger

import state_manager

def run_scan_and_open_trades(client, vagas_disponiveis: int):
    """Executa o ciclo de scan e abre novas posições (simulado)."""
    logger.info("--- Iniciando Etapa de Busca por Novos Ativos ---")
    trades_ativos = state_manager.ler_trades_ativos()
    simbolos_ativos = [trade['symbol'] for trade in trades_ativos]

    ativos_filtrados = buscar_e_filtrar_ativos(client)
    ativos_para_analise = [a for a in ativos_filtrados if a not in simbolos_ativos]

    if not ativos_para_analise:
        logger.info("Nenhum novo ativo encontrado para análise.")
        return

    logger.info(f"--- Iniciando Etapa de Análise e Score para {len(ativos_para_analise)} novos ativos ---")
    candidatos_finais = []
    for ativo in ativos_para_analise:
        logger.info(f"Analisando {ativo}...")
        score, df_analise, detalhes = analise_tecnica.calcular_score_ativo(client, ativo)

        log_detalhes = f"Score: {score} | Detalhes: {detalhes}"
        logger.debug(log_detalhes)

        if score > 0 and analise_tecnica.verificar_sinal_recente(df_analise):
            candidatos_finais.append({'symbol': ativo, 'score': score, 'detalhes': detalhes})
        else:
            logger.info(f" -> {ativo} descartado (score baixo ou sinal antigo).")

    candidatos_ordenados = sorted(candidatos_finais, key=lambda item: item['score'], reverse=True)

    if not candidatos_ordenados:
        logger.info("Nenhum novo candidato qualificado encontrado nesta rodada.")
        return

    logger.info(f"--- Processando {vagas_disponiveis} vagas para novas operações ---")
    for candidato in candidatos_ordenados:
        if vagas_disponiveis <= 0:
            logger.info("Todas as vagas disponíveis foram preenchidas.")
            break

        logger.info(f"Simulando abertura de trade para: {candidato['symbol']} (Score: {candidato['score']})")
        novo_trade = {
            "symbol": candidato['symbol'],
            "status": "ACTIVE", # Simulação direta para ACTIVE
            "entry_price": 1.0, # Preço simulado
            "quantity": config.VALOR_OPERACAO_USDT / 1.0, # Qtd simulada
            "entry_details": candidato['detalhes']
        }
        state_manager.adicionar_trade(novo_trade)
        vagas_disponiveis -= 1

def main():
    """
    Função principal que executa o robô em um loop contínuo.
    """
    logger.info("Iniciando o robô de trade para Binance v3.0 (Autônomo)...")
    client = conectar_binance()
    if not client:
        return

    while True:
        logger.info("="*50)
        logger.info(f"Iniciando novo ciclo de verificação: {datetime.now().isoformat()}")
        logger.info("="*50)

        # No futuro, aqui entrará a chamada ao position_manager

        trades_ativos = state_manager.ler_trades_ativos()
        vagas_disponiveis = config.QUANTIDADE_CRIPTOS_OPERAR - len(trades_ativos)

        logger.info(f"Memória: {len(trades_ativos)} trades ativos. Vagas: {vagas_disponiveis}")
        if vagas_disponiveis > 0:
            run_scan_and_open_trades(client, vagas_disponiveis)
        else:
            logger.info("Capacidade máxima de trades atingida. Nenhuma nova busca será feita.")

        try:
            # Lógica de sincronização com a próxima vela
            tf_em_minutos = int(''.join(filter(str.isdigit, config.TIMEFRAME)) or 1)
            if 'h' in config.TIMEFRAME:
                tf_em_minutos *= 60

            agora = datetime.now(timezone.utc)
            proxima_vela = (agora + timedelta(minutes=tf_em_minutos)).replace(
                minute=(agora.minute // tf_em_minutos) * tf_em_minutos,
                second=0, microsecond=0
            )
            if proxima_vela <= agora:
                proxima_vela += timedelta(minutes=tf_em_minutos)

            tempo_de_espera = (proxima_vela - agora).total_seconds() + 5 # Buffer de 5s

            logger.info(f"Ciclo concluído. Aguardando {tempo_de_espera // 60:.0f} minutos e {tempo_de_espera % 60:.0f} segundos para a próxima vela...")
            time.sleep(tempo_de_espera)
        except KeyboardInterrupt:
            logger.info("Robô interrompido pelo usuário. Desligando...")
            break
        except Exception as e:
            logger.critical(f"Ocorreu um erro CRÍTICO no loop principal: {e}. Aguardando 5 minutos antes de tentar novamente.")
            time.sleep(300)

if __name__ == "__main__":
    main()