# -*- coding: utf-8 -*-

import config
from binance.client import Client
import analise_tecnica
import discovery
import time
from datetime import datetime, timezone, timedelta
from logger_setup import logger
import state_manager
import order_manager
import position_manager

def conectar_binance():
    """Cria e retorna um cliente da API da Binance."""
    try:
        client = Client(config.API_KEY, config.API_SECRET)
        status = client.get_system_status()
        if status['status'] == 0:
            logger.info("Conexão com a Binance bem-sucedida!")
            return client
        else:
            logger.error(f"Erro ao conectar: {status['msg']}")
            return None
    except Exception as e:
        logger.error(f"Erro ao conectar com a API da Binance: {e}")
        return None

def buscar_e_filtrar_ativos(client):
    """Orquestra o processo de descoberta e filtragem de ativos."""
    try:
        tradable_symbols = discovery.get_tradable_spot_symbols(client)
        if not tradable_symbols: return []

        top_volume = discovery.discover_top_by_volume(client, tradable_symbols)
        if not top_volume: return []

        assets_antigos = discovery.filter_assets_by_age(client, top_volume)

        assets_finais = [s for s in assets_antigos if s not in getattr(config, 'LISTA_NEGRA', [])]
        logger.info(f"Encontrados {len(assets_finais)} ativos qualificados para análise.")
        return assets_finais
    except Exception as e:
        logger.error(f"Erro crítico ao buscar e filtrar ativos: {e}", exc_info=True)
        return []

def run_scan_and_open_trades(client, vagas_disponiveis: int):
    """Executa o ciclo de scan com logs avançados e lógica de entrada flexível."""
    logger.info("--- Iniciando Busca por Novos Ativos ---")
    simbolos_ativos = {trade['symbol'] for trade in state_manager.ler_trades_ativos()}
    simbolos_em_cooldown = state_manager.obter_ativos_em_cooldown()

    ativos_brutos = buscar_e_filtrar_ativos(client)

    # Filtra os ativos que já estão em operação ou em cooldown
    ativos_para_analise = [a for a in ativos_brutos if a not in simbolos_ativos and a not in simbolos_em_cooldown]

    if simbolos_em_cooldown:
        logger.info(f"Ativos em cooldown ignorados nesta análise: {', '.join(simbolos_em_cooldown)}")

    if not ativos_para_analise:
        logger.info("Nenhum novo ativo encontrado para análise.")
        return

    logger.info(f"Ativos a serem analisados: {', '.join(ativos_para_analise)}")
    logger.info(f"--- Iniciando Análise de Sinal Chilo (Idade Máx. do Sinal: {config.MAX_IDADE_SINAL_CANDLES} velas) ---")

    for symbol in ativos_para_analise:
        if vagas_disponiveis <= 0:
            logger.info("Todas as vagas de trade foram preenchidas.")
            break

        status, idade_sinal = analise_tecnica.get_chilo_signal_status(client, symbol)

        if status == analise_tecnica.SINAL_COMPRA:
            if idade_sinal <= config.MAX_IDADE_SINAL_CANDLES:
                logger.info(f" -> {symbol}: SINAL DE COMPRA VÁLIDO (iniciado há {idade_sinal} vela(s)). Tentando abrir trade...")
                resultado_ordem = order_manager.place_buy_order(
                    client, symbol=symbol, quote_order_qty=config.VALOR_OPERACAO_USDT
                )
                if resultado_ordem:
                    qty = resultado_ordem['quantity']
                    novo_trade = {
                        "symbol": resultado_ordem['symbol'],
                        "status": "ACTIVE",
                        "entry_price": resultado_ordem['entry_price'],
                        "quantity": qty,
                        "initial_quantity": qty,  # Salva a quantidade original
                        "next_target_index": 0,    # Começa mirando no primeiro alvo
                    }
                    state_manager.adicionar_trade(novo_trade)
                    vagas_disponiveis -= 1
                else:
                    logger.warning(f"Falha ao colocar ordem de compra para {symbol}.")
            else:
                logger.info(f" -> {symbol}: Sinal de compra antigo (iniciado há {idade_sinal} vela(s)). Ignorando.")
        else: # SEM_SINAL
            logger.info(f" -> {symbol}: Sem sinal de compra.")

def main():
    """Função principal que executa o robô em um loop contínuo."""
    logger.info("Iniciando o robô de trade para Binance...")
    client = conectar_binance()
    if not client: return

    while True:
        logger.info("="*50)
        logger.info(f"Iniciando novo ciclo: {datetime.now().isoformat()}")

        trades_ativos = state_manager.ler_trades_ativos()
        position_manager.check_active_positions(client, trades_ativos)

        trades_ativos = state_manager.ler_trades_ativos()
        vagas_disponiveis = config.QUANTIDADE_CRIPTOS_OPERAR - len(trades_ativos)

        logger.info(f"Memória: {len(trades_ativos)} trades ativos. Vagas: {vagas_disponiveis}")
        if vagas_disponiveis > 0:
            run_scan_and_open_trades(client, vagas_disponiveis)
        else:
            logger.info("Capacidade máxima de trades atingida.")

        try:
            tf_map = {'h': 60, 'd': 1440, 'm': 1}
            timeframe_lower = config.TIMEFRAME.lower()
            multiplier = tf_map.get(timeframe_lower[-1], 1)
            tf_em_minutos = int(timeframe_lower[:-1]) * multiplier

            agora = datetime.now(timezone.utc)
            proximo_fechamento = (agora + timedelta(minutes=tf_em_minutos)).replace(
                minute=(agora.minute // tf_em_minutos) * tf_em_minutos, second=0, microsecond=0
            )
            if proximo_fechamento <= agora:
                proximo_fechamento += timedelta(minutes=tf_em_minutos)

            tempo_de_espera = (proximo_fechamento - agora).total_seconds() + 5
            logger.info(f"Ciclo concluído. Aguardando {tempo_de_espera // 60:.0f}m {tempo_de_espera % 60:.0f}s para a próxima vela.")
            time.sleep(tempo_de_espera)
        except KeyboardInterrupt:
            logger.info("Robô interrompido pelo usuário.")
            break
        except Exception as e:
            logger.critical(f"Erro crítico no loop principal: {e}. Aguardando 5 min.", exc_info=True)
            time.sleep(300)

if __name__ == "__main__":
    main()
