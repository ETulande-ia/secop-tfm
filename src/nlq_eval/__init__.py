"""
Evaluación de lenguaje ciudadano. No modifica el NLQ del asistente.

Funciones:
- cargar_excel(): Lee las expresiones del Excel.
- partir(): Separa las 51 de desarrollo y las 26 reservadas.
- diagnosticar_chat(): Comprueba el acceso a POST /api/chat.
- preguntar_chat(): Envía una consulta al asistente.
- evaluar_linea_base(): Ejecuta o reutiliza la evaluación v1.
- evaluar_v2(): Compara una segunda corrida sin pisar v1.
"""

from .cliente import diagnosticar_chat, preguntar_chat
from .evaluar import evaluar_linea_base, evaluar_v2
from .particion import IDS_RESERVADOS, cargar_excel, partir

__all__ = [
    "IDS_RESERVADOS",
    "cargar_excel",
    "partir",
    "diagnosticar_chat",
    "preguntar_chat",
    "evaluar_linea_base",
    "evaluar_v2",
]
