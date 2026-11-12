"""
config/frases.py
================
Frase do dia da barra lateral: uma por dia, a mesma para todos, trocando à meia-noite.
Para trocar, tirar ou acrescentar frases basta editar FRASES; o ciclo se ajusta ao tamanho da lista.
A ordem sorteada é fixa (mesma semente), então os dias seguidos não seguem um tema só.
"""

import random
from datetime import date

FRASES = [
    # começar e persistir
    "Todo dia é uma nova chance de fazer um pouco melhor do que ontem.",
    "Comece pelo que está ao seu alcance. O resto vai aparecendo no caminho.",
    "Um passo por dia é o caminho mais curto para qualquer lugar.",
    "Constância vence talento quando o talento se cansa.",
    "Persistir não é repetir; é melhorar a cada tentativa.",
    "O progresso quase nunca faz barulho, mas nunca para.",
    "Quando o dia pesar, lembre-se de por que você começou.",
    "Pequenos acertos acumulados valem mais do que um grande golpe de sorte.",
    "Hoje é um bom dia para fazer acontecer.",
    "Não espere estar pronto: comece e você vai ficando.",
    # propósito e orgulho do que faz
    "Trabalhar com propósito torna o difícil mais leve.",
    "Faça hoje algo de que o seu eu de amanhã vá se orgulhar.",
    "Fazer bem feito é a forma mais simples de respeitar o próprio trabalho.",
    "Todo grande resultado começou com uma tarefa pequena bem feita.",
    "O seu esforço de hoje é o resultado que alguém vai usar amanhã.",
    "Quem trabalha com honestidade dorme tranquilo.",
    "Capricho é o que transforma tarefa em trabalho de que você se orgulha.",
    "O que você faz importa mais do que você imagina.",
    # equipe
    "Trabalho em equipe transforma cada área em parte da mesma engrenagem.",
    "Sozinhos vamos rápido; juntos vamos longe.",
    "Reconhecer o trabalho do colega também é trabalho, e dos bons.",
    "Ajudar alguém a crescer é a melhor forma de crescer junto.",
    "Uma equipe unida resolve em uma hora o que três separadas levam um dia.",
    "Gentileza no trabalho custa pouco e rende muito.",
    "O que você ensina hoje, a equipe usa para sempre.",
    "Um bom dia de trabalho também se faz com bom humor.",
    # superação
    "Errar faz parte; aprender com o erro é o que importa.",
    "Cada problema resolvido deixa uma ferramenta nova na caixa.",
    "Dificuldade é só o caminho pedindo um pouco mais de você.",
    "Quem se prepara bem encontra menos obstáculos, e vence os que aparecem.",
    "A paciência também é uma forma de produtividade.",
    "Nenhuma tarefa é grande demais quando dividida em passos.",
    "O cansaço passa; o orgulho de ter terminado fica.",
    "A disciplina de hoje é a liberdade de amanhã.",
    # crescer
    "Aprender é o único investimento que ninguém consegue tirar de você.",
    "Pergunte sem medo: toda resposta é um degrau.",
    "Curiosidade é o melhor combustível de uma boa carreira.",
    "Foco é dizer sim ao que importa e não ao que distrai.",
    "Cada dia de trabalho é uma página da sua história profissional. Escreva bem.",
    "O melhor momento para começar a melhorar é agora.",
]

_ORDEM = list(range(len(FRASES)))
random.Random(2026).shuffle(_ORDEM)


def frase_do_dia(dia: date | None = None) -> tuple[str, int, int]:
    """(texto, posição, total) da frase de hoje. Mesma para todos no mesmo dia; ciclo do tamanho da lista."""
    dia = dia or date.today()
    total = len(FRASES)
    posicao = dia.toordinal() % total
    return FRASES[_ORDEM[posicao]], posicao + 1, total
