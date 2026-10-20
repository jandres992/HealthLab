"""
Servicios transaccionales del laboratorio (RNF-29 a RNF-31, RNF-38.1).

Cada función es un caso de uso completo: abre `transaction.atomic()`, bloquea
las filas que va a modificar, valida la transición en `domain/`, escribe,
notifica y audita en la misma transacción. Las vistas solo llaman al servicio.
"""
