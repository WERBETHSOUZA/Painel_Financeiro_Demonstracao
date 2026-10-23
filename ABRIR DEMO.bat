@echo off
chcp 65001 >nul
title Painel Financeiro - DEMONSTRACAO (dados ficticios)

cd /d "%~dp0"

echo.
echo  Abrindo a demonstracao com DADOS FICTICIOS (sem banco de dados; login: admin / admin).
echo  Endereco: http://localhost:8590
echo  Para encerrar, feche esta janela.
echo.

start "" http://localhost:8590
python -m streamlit run app_demo.py --server.port 8590 --server.headless true

pause

