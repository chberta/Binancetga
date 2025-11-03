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

def buscar_e_filtrar_ativos(client):
    """
    Orquestra o processo de descoberta e filtragem de ativos conforme a nova estratégia.
    1. Busca os 100 ativos com maior volume.
    2. Filtra para manter apenas os que têm mais de 52 semanas.
    """
    try:
        # Etapa 1: Obter todos os símbolos negociáveis
        tradable_symbols = discovery.get_tradable_spot_symbols(client)
        if not tradable_symbols:
            logger.warning("Nenhum símbolo negociável encontrado. Interrompendo a busca.")
            return []

        # Etapa 2: Descobrir os 100 principais por volume
        top_100_volume = discovery.discover_top_by_volume(client, tradable_symbols)
        if not top_100_volume:
            logger.warning("Não foi possível obter a lista de ativos por volume.")
            return []

        # Etapa 3: Filtrar por idade (mais de 52 semanas)
        assets_antigos = discovery.filter_assets_by_age(client, top_100_volume, min_weeks_old=52)

        # Etapa 4: (Opcional) Aplicar lista negra
        if hasattr(config, 'LISTA_NEGRA'):
            assets_finais = [symbol for symbol in assets_antigos if symbol not in config.LISTA_NEGRA]
            logger.info(f"{len(assets_antigos) - len(assets_finais)} ativos foram removidos pela lista negra.")
        else:
            assets_finais = assets_antigos

        logger.info(f"Encontrados {len(assets_finais)} ativos que atendem a TODOS os critérios e foram selecionados para análise.")
        return assets_finais

    except Exception as e:
        logger.error(f"Ocorreu um erro crítico ao buscar e filtrar ativos: {e}", exc_info=True)
        return []

import time
from datetime import datetime, timedelta, timezone
from logger_setup import logger

import state_manager
import order_manager
import position_manager

def run_scan_and_open_trades(client, vagas_disponiveis: int):
    """
    Executa o ciclo de scan e abre novas posições baseado na estratégia Chilo RSI.
    """
    logger.info("--- Iniciando Etapa de Busca por Novos Ativos ---")
    # 1. Obter a lista de ativos já em operação para não analisá-los novamente.
    trades_ativos = state_manager.ler_trades_ativos()
    simbolos_ativos = [trade['symbol'] for trade in trades_ativos]

    # 2. Buscar e filtrar a lista de potenciais ativos.
    ativos_filtrados = buscar_e_filtrar_ativos(client)
    ativos_para_analise = [a for a in ativos_filtrados if a not in simbolos_ativos]

    if not ativos_para_analise:
        logger.info("Nenhum novo ativo encontrado para análise (já estamos em todos ou nenhum passou no filtro).")
        return

    logger.info(f"--- Iniciando Análise de Sinal Chilo para {len(ativos_para_analise)} ativos ---")

    # 3. Analisa cada ativo e tenta abrir a operação se houver sinal.
    for symbol in ativos_para_analise:
        if vagas_disponiveis <= 0:
            logger.info("Todas as vagas de trade foram preenchidas.")
            break

        logger.info(f"Analisando {symbol}...")

        # 4. Verifica se há um sinal de compra recente.
        if analise_tecnica.verificar_sinal_chilo_recente(client, symbol):
            logger.info(f"SINAL DE COMPRA ENCONTRADO para {symbol}. Tentando abrir trade...")

            # 5. Executar a ordem de compra.
            resultado_ordem = order_manager.place_buy_order(
                client,
                symbol=symbol,
                quote_order_qty=config.VALOR_OPERACAO_USDT
            )

            # 6. Se a ordem for bem-sucedida, adicionar ao estado.
            if resultado_ordem:
                novo_trade = {
                    "symbol": resultado_ordem['symbol'],
                    "status": "ACTIVE",
                    "entry_price": resultado_ordem['entry_price'],
                    "quantity": resultado_ordem['quantity'],
                }
                state_manager.adicionar_trade(novo_trade)
                vagas_disponiveis -= 1 # Decrementa o número de vagas.
            else:
                logger.warning(f"Falha ao colocar ordem de compra para {symbol}. O sinal será ignorado.")
        else:
            logger.info(f" -> {symbol} sem sinal de compra recente.")

def main():
    """
    Função principal que executa o robô em um loop contínuo.
    """
    logger.info("Iniciando o robô de trade para Binance v4.0 (Trading Integrado)...")
    client = conectar_binance()
    if not client:
        return

    while True:
        logger.info("="*50)
        logger.info(f"Iniciando novo ciclo de verificação: {datetime.now().isoformat()}")
        logger.info("="*50)

        # 1. Gerenciar posições existentes (verificar TP/SL)
        trades_ativos = state_manager.ler_trades_ativos()
        position_manager.check_active_positions(client, trades_ativos)

        # Recarrega o estado caso o position_manager tenha fechado trades
        trades_ativos = state_manager.ler_trades_ativos()
        vagas_disponiveis = config.QUANTIDADE_CRIPTOS_OPERAR - len(trades_ativos)

        # 2. Procurar por novas oportunidades se houver vagas
        logger.info(f"Memória: {len(trades_ativos)} trades ativos. Vagas: {vagas_disponiveis}")
        if vagas_disponiveis > 0:
            run_scan_and_open_trades(client, vagas_disponiveis)
        else:
            logger.info("Capacidade máxima de trades atingida. Nenhuma nova busca será feita.")

        # 3. Aguardar o próximo ciclo
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