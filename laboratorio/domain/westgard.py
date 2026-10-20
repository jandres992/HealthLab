"""
Reglas de Westgard sobre una serie de z-scores (RF-50).

`evaluar(serie)` recibe los z-scores de un mismo material de control (nivel),
del más antiguo al más reciente, con la corrida nueva al final. Devuelve
('aceptada' | 'advertencia' | 'rechazada', [reglas violadas]).

Reglas de rechazo: 1-3s, 2-2s, R-4s, 4-1s, 10x. Advertencia: 1-2s.
"""
from decimal import Decimal


def z_score(valor, media, desviacion):
    valor, media, desviacion = Decimal(str(valor)), Decimal(str(media)), Decimal(str(desviacion))
    if desviacion == 0:
        return Decimal('0')
    return ((valor - media) / desviacion).quantize(Decimal('0.001'))


def evaluar(serie):
    serie = [Decimal(str(z)) for z in serie]
    if not serie:
        return 'aceptada', []
    reglas = []
    z = serie[-1]

    if abs(z) > 3:
        reglas.append('1-3s')
    if len(serie) >= 2:
        a, b = serie[-2], serie[-1]
        if abs(a) > 2 and abs(b) > 2 and (a > 0) == (b > 0):
            reglas.append('2-2s')
        if (a > 2 and b < -2) or (a < -2 and b > 2):
            reglas.append('R-4s')
    if len(serie) >= 4:
        ultimos = serie[-4:]
        if all(v > 1 for v in ultimos) or all(v < -1 for v in ultimos):
            reglas.append('4-1s')
    if len(serie) >= 10:
        ultimos = serie[-10:]
        if all(v > 0 for v in ultimos) or all(v < 0 for v in ultimos):
            reglas.append('10x')

    if reglas:
        return 'rechazada', reglas
    if abs(z) > 2:
        return 'advertencia', ['1-2s']
    return 'aceptada', []
