# -*- coding: utf-8 -*-

"""
Script de Teste para a Nova Estratégia de Descoberta e Filtro

Este script executa a função 'buscar_e_filtrar_ativos' do main.py
para validar todo o fluxo de descoberta:
1. Top 100 por volume.
2. Filtro de idade (> 52 semanas).
3. Filtro de lista negra.
"""

import main
from logger_setup import logger

def run_test():
    """
    Executa o teste de ponta a ponta da descoberta de ativos.
    """
    logger.info("--- Iniciando Teste de Descoberta e Filtragem de Ativos ---")

    client = main.conectar_binance()
    if not client:
        logger.error("Falha ao conectar. Encerrando teste.")
        return

    try:
        # Chama a função principal que orquestra toda a lógica
        ativos_aprovados = main.buscar_e_filtrar_ativos(client)

        logger.info("\n" + "="*50)
        logger.info("--- Lista Final de Ativos Aprovados ---")
        if ativos_aprovados:
            for i, symbol in enumerate(ativos_aprovados):
                logger.info(f"{i+1:3d}. {symbol}")
        else:
            logger.info("(Nenhum ativo aprovado)")
        logger.info("="*50)

    except Exception as e:
        logger.error(f"\nOcorreu um erro geral durante o teste: {e}", exc_info=True)

if __name__ == "__main__":
    run_test()