"""
Lucho Agent Tools — what Lucho can DO.

Each tool has two parts:
1. Schema (OpenAI/DeepSeek function-calling format) — what the LLM sees
2. Handler (async Python function) — what actually executes (DETERMINISTIC)

The LLM decides WHICH tool to call and WITH WHAT parameters.
The handler does the actual database work. The LLM NEVER generates SQL.

Multi-tenant: every handler takes user_id and filters by it.
All handlers return structured dicts that the LLM uses to craft the response.
"""

import logging
from typing import Any

from app.services.persistence import (
    persist_document,
    persist_event,
    persist_list_items,
    persist_note,
)
from app.services.search import (
    semantic_search,
    upcoming_deadlines,
    list_pending_items,
    search_by_text,
)
from app.services.vehicle_rules import evaluate_vehicle_rules
from app.services.embeddings import generate_embedding

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL SCHEMAS — what the LLM sees (OpenAI/DeepSeek function-calling format)
# =============================================================================

TOOL_SAVE_VEHICLE = {
    "type": "function",
    "function": {
        "name": "save_vehicle",
        "description": "Guardar un vehículo del usuario. Lucho calcula automáticamente la fecha de matriculación, pico y placa, SOAT y RTV. Usar cuando el usuario menciona una placa de auto o moto ecuatoriana (formato ABC-1234 o ABC-123).",
        "parameters": {
            "type": "object",
            "properties": {
                "plate": {
                    "type": "string",
                    "description": "Placa del vehículo en formato ecuatoriano. Ej: PBC-1234, ABC-123.",
                },
                "brand": {
                    "type": "string",
                    "description": "Marca del vehículo. Ej: Toyota, Chevrolet, Kia.",
                },
                "model": {
                    "type": "string",
                    "description": "Modelo del vehículo. Ej: Corolla, Grand Vitara.",
                },
                "year": {
                    "type": "integer",
                    "description": "Año del vehículo. Ej: 2020.",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas adicionales sobre el vehículo.",
                },
            },
            "required": ["plate"],
        },
    },
}

TOOL_SAVE_DOCUMENT = {
    "type": "function",
    "function": {
        "name": "save_document",
        "description": "Guardar un documento personal del usuario: cédula de identidad, pasaporte, licencia de conducir, SOAT, garantía, factura, o cualquier documento con fecha de vencimiento. SIEMPRE pasá el file_key si viene de analyze_image o de un archivo adjunto.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_type": {
                    "type": "string",
                    "description": "Tipo de documento. Ej: cedula, pasaporte, licencia, soat, garantia, factura, otro.",
                },
                "name": {
                    "type": "string",
                    "description": "Nombre descriptivo del documento. Ej: 'Cédula de Patricio', 'SOAT del carro'.",
                },
                "document_number": {
                    "type": "string",
                    "description": "Número del documento si el usuario lo menciona. Ej: '1712345678' para cédula, 'PBC-1234' para SOAT.",
                },
                "expiry_date": {
                    "type": "string",
                    "description": "Fecha de vencimiento en formato YYYY-MM-DD, si aplica.",
                },
                "entity_name": {
                    "type": "string",
                    "description": "Nombre de la entidad emisora. Ej: 'Registro Civil', 'ANT', 'Seguros Equinoccial'.",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas adicionales.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Etiquetas para organizar. Ej: ['personal', 'legal', 'familia'].",
                },
                "file_key": {
                    "type": "string",
                    "description": "Clave del archivo en MinIO. Viene del resultado de analyze_image o del mensaje [foto: X]. Formato: 'user_id/photo_123.jpg'. SIEMPRE incluir este campo si el usuario envió una foto.",
                },
            },
            "required": ["document_type", "name"],
        },
    },
}

TOOL_LIST_MY_DOCUMENTS = {
    "type": "function",
    "function": {
        "name": "list_my_documents",
        "description": "Listar los documentos del usuario con filtros por tipo y estado. Usar cuando pregunta '¿qué documentos tengo?', 'mis documentos', 'mostrame mis SOAT', '¿qué documentos me vencen pronto?'.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_type": {
                    "type": "string",
                    "description": "Filtrar por tipo: cedula, pasaporte, licencia, soat, seguro, factura, garantia, certificado, escritura, contrato, tarjeta, otro. Opcional.",
                },
                "status": {
                    "type": "string",
                    "enum": ["all", "active", "expiring_soon", "expired"],
                    "description": "Estado. Default: 'all'. 'expiring_soon' = vence en 30 días.",
                },
            },
            "required": [],
        },
    },
}

TOOL_SAVE_EVENT = {
    "type": "function",
    "function": {
        "name": "save_event",
        "description": "Guardar un evento, cita, reunión, o recordatorio con fecha. El usuario será notificado automáticamente unos días antes. Si el usuario adjuntó una foto (receta médica, invitación, captura), pasá el file_key para vincularla.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título corto del evento. Ej: 'Cita dentista', 'Reunión banco'.",
                },
                "target_date": {
                    "type": "string",
                    "description": "Fecha del evento en formato YYYY-MM-DD. Calculá desde la fecha actual. 'mañana' = día siguiente, 'el lunes' = próximo lunes, 'en dos semanas' = +14 días.",
                },
                "description": {
                    "type": "string",
                    "description": "Descripción adicional del evento.",
                },
                "recurrence": {
                    "type": "string",
                    "description": "Si el evento se repite. Opciones: 'none', 'daily', 'weekly', 'monthly', 'yearly'.",
                },
                "file_key": {
                    "type": "string",
                    "description": "Clave de foto en MinIO si el usuario adjuntó una imagen. Formato: 'user_id/photo_123.jpg'.",
                },
            },
            "required": ["title", "target_date"],
        },
    },
}

TOOL_LIST_MY_EVENTS = {
    "type": "function",
    "function": {
        "name": "list_my_events",
        "description": "Listar los eventos del usuario con filtros. Usar cuando pregunta '¿qué tengo esta semana?', 'mis eventos', '¿qué citas tengo?', 'próximos eventos'.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["upcoming", "done", "cancelled", "overdue", "all"],
                    "description": "Filtrar por estado. Default: 'upcoming'.",
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "tomorrow", "this_week", "next_week", "this_month", "all"],
                    "description": "Período. Default: 'all' (próximos 90 días).",
                },
            },
            "required": [],
        },
    },
}

TOOL_SAVE_LIST = {
    "type": "function",
    "function": {
        "name": "save_list",
        "description": "Guardar ítems en una lista (compras, tareas, pendientes, deseos). Si la lista no existe, se crea automáticamente.",
        "parameters": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista. Ej: 'compras', 'pendientes', 'supermaxi', 'deseos'.",
                },
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de ítems a agregar. Ej: ['leche', 'pan', 'huevos'].",
                },
                "quantity": {
                    "type": "string",
                    "description": "Cantidad si todos los ítems comparten la misma cantidad. Ej: '2 libras'.",
                },
            },
            "required": ["list_name", "items"],
        },
    },
}

TOOL_LIST_MY_NOTES = {
    "type": "function",
    "function": {
        "name": "list_my_notes",
        "description": "Listar las notas del usuario agrupadas por tema. Usar cuando pregunta '¿qué notas tengo?', 'mis apuntes de cocina', '¿qué ideas guardé?', 'mostrame mis notas de tecnología'.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Filtrar por tema. Si no se pasa, muestra todas las notas agrupadas por tema.",
                },
            },
            "required": [],
        },
    },
}

TOOL_DELETE_NOTE = {
    "type": "function",
    "function": {
        "name": "delete_note",
        "description": "Eliminar una nota específica. Usar SOLO cuando el usuario pide explícitamente 'elimina la nota de...', 'borra el apunte de...', 'ya no necesito esa nota'.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Tema donde está la nota.",
                },
                "search": {
                    "type": "string",
                    "description": "Palabra o frase para encontrar la nota a eliminar. Busca en el contenido.",
                },
            },
            "required": ["topic", "search"],
        },
    },
}

TOOL_LIST_ITEMS = {
    "type": "function",
    "function": {
        "name": "list_items",
        "description": "Consultar ítems de una lista específica o de todas las listas. Usar cuando el usuario pregunta '¿qué tengo en compras?', 'mis pendientes', '¿qué me falta?', '¿qué listas tengo?'.",
        "parameters": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista a consultar. Si no se pasa, muestra todas las listas del usuario.",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "done", "all"],
                    "description": "Filtrar por estado. Default: 'pending' (solo lo que falta). Usar 'done' para ver completados, 'all' para todo.",
                },
            },
            "required": [],
        },
    },
}

TOOL_COMPLETE_ITEM = {
    "type": "function",
    "function": {
        "name": "complete_item",
        "description": "Marcar uno o varios ítems como completados (done). Usar cuando el usuario dice 'ya compré X', 'listo Y', 'completé Z', 'marqué como hecho W'.",
        "parameters": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Lista donde están los ítems. Si no se pasa, busca en todas las listas del usuario.",
                },
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ítems a marcar como completados. Ej: ['leche', 'pan']. Busca coincidencia parcial en el contenido.",
                },
                "mark_all": {
                    "type": "boolean",
                    "description": "Si es true, marca TODOS los ítems pendientes de la lista como completados. Usar cuando dice 'completé todo', 'ya hice todo lo de X'.",
                },
            },
            "required": ["items"],
        },
    },
}

TOOL_DELETE_LIST = {
    "type": "function",
    "function": {
        "name": "delete_list",
        "description": "Eliminar una lista completa y todos sus ítems. Usar SOLO cuando el usuario pide explícitamente 'elimina la lista X', 'borra la lista Y', 'ya no necesito la lista Z'.",
        "parameters": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre exacto de la lista a eliminar.",
                },
            },
            "required": ["list_name"],
        },
    },
}

TOOL_SAVE_NOTE = {
    "type": "function",
    "function": {
        "name": "save_note",
        "description": "Guardar una nota, idea, reflexión o información libre del usuario, organizada por tema. Si el usuario adjuntó una foto, pasá el file_key para vincularla a la nota.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Tema o categoría de la nota. Ej: 'ideas de negocio', 'recetas', 'salud', 'general'.",
                },
                "content": {
                    "type": "string",
                    "description": "Contenido completo de la nota.",
                },
                "file_key": {
                    "type": "string",
                    "description": "Clave de foto en MinIO si el usuario adjuntó una imagen. Formato: 'user_id/photo_123.jpg'.",
                },
            },
            "required": ["topic", "content"],
        },
    },
}

TOOL_SEARCH_DATA = {
    "type": "function",
    "function": {
        "name": "search_my_data",
        "description": "Buscar en TODOS los datos del usuario: vehículos, documentos, eventos, notas, listas, gastos. Usar cuando el usuario pregunta por algo que ya guardó (¿cuándo vence mi SOAT?, ¿qué tengo pendiente?, ¿cuál es mi pico y placa?, busca mis notas de...).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Lo que el usuario está buscando, en sus propias palabras.",
                },
                "search_type": {
                    "type": "string",
                    "description": "Tipo de búsqueda. Opciones: 'deadlines' (vencimientos), 'pending' (pendientes), 'notes' (notas), 'vehicles' (vehículos), 'all' (todo). Si no estás seguro, usar 'all'.",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_GET_SUMMARY = {
    "type": "function",
    "function": {
        "name": "get_my_summary",
        "description": "Obtener un resumen rápido de todo lo que el usuario tiene: vehículos, próximos vencimientos, pendientes. Útil cuando el usuario pregunta '¿qué tengo?', 'resumen', '¿cómo voy?'.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_ANALYZE_IMAGE = {
    "type": "function",
    "function": {
        "name": "analyze_image",
        "description": "Analizar una imagen o documento que el usuario envió y extraer datos estructurados. Usar cuando el usuario envía una foto de un documento (SOAT, factura, cédula, licencia, garantía, matrícula) y quiere que Lucho extraiga la información. El parámetro file_key viene del contexto del mensaje.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_key": {
                    "type": "string",
                    "description": "Clave del archivo en MinIO (viene en el mensaje del usuario como 'minio://...').",
                },
                "hint": {
                    "type": "string",
                    "description": "Pista del usuario sobre qué tipo de documento es. Ej: 'factura del súper', 'mi SOAT', 'la garantía de la lavadora'.",
                },
            },
            "required": ["file_key"],
        },
    },
}

TOOL_SEARCH_CONVERSATION = {
    "type": "function",
    "function": {
        "name": "search_conversation",
        "description": "Buscar en el historial de conversaciones del usuario. Usar cuando el usuario pregunta '¿qué te dije sobre...?', '¿recuerdas cuando hablamos de...?', 'busca en el chat...'.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Palabras o frase a buscar en el historial. Ej: 'carro', 'cita dentista', 'factura'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Cantidad máxima de resultados. Default: 5.",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_SAVE_PROJECT_TASK = {
    "type": "function",
    "function": {
        "name": "save_project_task",
        "description": "Guardar una tarea en un proyecto. Si el proyecto no existe, se crea automáticamente. Usar cuando el usuario menciona un proyecto y una tarea: 'para el proyecto X necesito hacer Y', 'agrega esto a mi proyecto Z'.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nombre del proyecto. Ej: 'casa nueva', 'tesis', 'evento boda'.",
                },
                "content": {
                    "type": "string",
                    "description": "Descripción de la tarea. Ej: 'contratar albañil', 'revisar catering'.",
                },
                "due_date": {
                    "type": "string",
                    "description": "Fecha límite en formato YYYY-MM-DD, si aplica.",
                },
            },
            "required": ["project_name", "content"],
        },
    },
}

TOOL_LIST_PROJECT_TASKS = {
    "type": "function",
    "function": {
        "name": "list_project_tasks",
        "description": "Listar las tareas de un proyecto o de todos los proyectos del usuario. Usar cuando el usuario pregunta '¿cómo va mi proyecto X?', '¿qué tengo pendiente del proyecto Y?', 'muéstrame mis proyectos'.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nombre del proyecto a consultar. Si no se especifica, lista todos los proyectos.",
                },
                "status": {
                    "type": "string",
                    "description": "Filtrar por estado: 'pending', 'done', o 'all'. Default: 'all'.",
                },
            },
            "required": [],
        },
    },
}

TOOL_COMPLETE_PROJECT_TASK = {
    "type": "function",
    "function": {
        "name": "complete_project_task",
        "description": "Marcar una tarea de proyecto como completada. Usar cuando el usuario dice 'ya terminé X del proyecto Y', 'marca como hecho Z'.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nombre del proyecto.",
                },
                "task_content": {
                    "type": "string",
                    "description": "Contenido de la tarea a marcar como completada (o parte del contenido para buscarla).",
                },
            },
            "required": ["project_name", "task_content"],
        },
    },
}

TOOL_REOPEN_PROJECT_TASK = {
    "type": "function",
    "function": {
        "name": "reopen_project_task",
        "description": "Reabrir una tarea completada (done → pending). Usar cuando el usuario dice 'me equivoqué, X todavía no está lista', 'reabre la tarea Y', 'desmarca Z como completada'.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nombre del proyecto donde está la tarea.",
                },
                "task_content": {
                    "type": "string",
                    "description": "Contenido de la tarea a reabrir (busca por coincidencia parcial en tareas completadas).",
                },
            },
            "required": ["project_name", "task_content"],
        },
    },
}

TOOL_ARCHIVE_PROJECT = {
    "type": "function",
    "function": {
        "name": "archive_project",
        "description": "Archivar un proyecto completo (ya no aparece en listados). Usar cuando el usuario dice 'ya terminé el proyecto X', 'archiva el proyecto Y', 'cerra el proyecto Z'. Las tareas no se borran.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "Nombre del proyecto a archivar.",
                },
            },
            "required": ["project_name"],
        },
    },
}

TOOL_SAVE_CONTACT = {
    "type": "function",
    "function": {
        "name": "save_contact",
        "description": "Guardar un contacto personal: nombre, teléfono, email, WhatsApp, relación (amigo, familia, colega). Usar cuando el usuario quiere guardar información de contacto de alguien.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre completo del contacto.",
                },
                "phone_number": {
                    "type": "string",
                    "description": "Número de teléfono. Formato internacional o local.",
                },
                "email": {
                    "type": "string",
                    "description": "Dirección de correo electrónico.",
                },
                "whatsapp_id": {
                    "type": "string",
                    "description": "Número de WhatsApp (si es distinto del teléfono).",
                },
                "relationship": {
                    "type": "string",
                    "description": "Tipo de relación: 'amigo', 'familia', 'colega', 'cliente', 'proveedor', etc.",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas adicionales: cumpleaños, dirección, empresa, etc.",
                },
            },
            "required": ["name"],
        },
    },
}

TOOL_LIST_CONTACTS = {
    "type": "function",
    "function": {
        "name": "list_contacts",
        "description": "Listar los contactos guardados. Usar cuando el usuario pregunta '¿qué contactos tengo?', 'buscame el teléfono de X', 'mis contactos'.",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Buscar por nombre o relación. Si no se especifica, lista todos.",
                },
                "relationship": {
                    "type": "string",
                    "description": "Filtrar por relación: 'amigo', 'familia', 'colega'.",
                },
            },
            "required": [],
        },
    },
}

TOOL_DELETE_CONTACT = {
    "type": "function",
    "function": {
        "name": "delete_contact",
        "description": "Eliminar un contacto. Usar SOLO cuando el usuario pide explícitamente 'elimina a X', 'borra el contacto de Y', 'ya no necesito a Z'.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nombre del contacto a eliminar. Busca coincidencia exacta.",
                },
            },
            "required": ["name"],
        },
    },
}

TOOL_UPDATE_LAST = {
    "type": "function",
    "function": {
        "name": "update_last",
        "description": "Corregir o actualizar la última entidad que se guardó. Usar cuando el usuario dice 'no, era...', 'corregí...', 'cambiale...'.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "description": "Tipo de entidad a corregir: 'event', 'note', 'list', 'asset', 'expense'.",
                },
                "field": {
                    "type": "string",
                    "description": "Campo a modificar. Ej: 'title', 'target_date', 'content', 'plate'.",
                },
                "new_value": {
                    "type": "string",
                    "description": "Nuevo valor para el campo.",
                },
            },
            "required": ["entity_type", "field", "new_value"],
        },
    },
}

TOOL_CHECK_VEHICLE_INFO = {
    "type": "function",
    "function": {
        "name": "check_vehicle_info",
        "description": "Consultar información oficial de un vehículo ecuatoriano por placa: datos del SRI (marca, modelo, año, cilindraje, último año pagado), datos de matriculación (fechas, estado, cantón), y multas de tránsito ANT pendientes. Usar cuando el usuario pregunta por un vehículo específico o quiere saber si tiene multas.",
        "parameters": {
            "type": "object",
            "properties": {
                "plate": {
                    "type": "string",
                    "description": "Placa del vehículo sin guión. Ej: 'ABJ1245', 'PBC1234'.",
                },
            },
            "required": ["plate"],
        },
    },
}

TOOL_SEND_PHOTO = {
    "type": "function",
    "function": {
        "name": "send_photo",
        "description": "Enviar una foto O documento (PDF, DOC) al usuario. Funciona para cualquier tipo de archivo guardado. Usar cuando el usuario pide ver, descargar o recibir algo: 'pasame mi cédula', 'mostrame el SOAT', 'enseñame la factura', 'descargar el PDF', 'quiero ver el documento', 'mandame el archivo'. El file_key viene de los resultados de búsqueda.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_key": {
                    "type": "string",
                    "description": "Clave del archivo en MinIO (aplica a fotos JPG/PNG Y documentos PDF/DOC). Viene de los resultados de búsqueda como 'file_key'. Ej: 'user_id/photo_123.jpg' o 'user_id/doc_456_factura.pdf'.",
                },
                "caption": {
                    "type": "string",
                    "description": "Texto descriptivo para acompañar la foto. Ej: 'Tu cédula de identidad', 'SOAT del PBC-1234'.",
                },
            },
            "required": ["file_key"],
        },
    },
}

TOOL_WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Buscar CUALQUIER cosa en internet — sin restricciones de tema. Deportes, restaurantes, cultura, historia, trámites, noticias, LO QUE SEA. Es gratis. Usar siempre que el usuario pregunte algo que no está en sus datos personales. Respondé con los resultados en 1-2 líneas y ofrecé guardar algo relacionado.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Consulta en español. Ej: 'mejores restaurantes Cuenca Ecuador', 'capital de Francia', 'quién ganó el mundial 2026'.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Cantidad máxima de resultados. Default: 5, máximo: 8.",
                },
            },
            "required": ["query"],
        },
    },
}

TOOL_LIST_MY_VEHICLES = {
    "type": "function",
    "function": {
        "name": "list_my_vehicles",
        "description": "Mostrar los vehículos del usuario con datos clave: pico y placa, matriculación, SOAT, RTV. Usar cuando el usuario pregunta '¿qué carros tengo?', '¿cómo están mis vehículos?', o quiere ver información de sus vehículos guardados.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_ADD_MAINTENANCE = {
    "type": "function",
    "function": {
        "name": "add_maintenance",
        "description": "Registrar un mantenimiento de un vehículo: cambio de aceite, frenos, llantas, batería, general. Incluye costo, kilometraje, taller y fecha del mantenimiento. El usuario puede subir la factura como foto.",
        "parameters": {
            "type": "object",
            "properties": {
                "vehicle_id_or_plate": {
                    "type": "string",
                    "description": "ID del vehículo o placa para identificar cuál vehículo. Ej: 'PBC1234'.",
                },
                "maintenance_type": {
                    "type": "string",
                    "description": "Tipo de mantenimiento: oil_change, brakes, tires, battery, general, other.",
                    "enum": ["oil_change", "brakes", "tires", "battery", "general", "other"],
                },
                "description": {
                    "type": "string",
                    "description": "Descripción de qué se hizo.",
                },
                "cost": {
                    "type": "number",
                    "description": "Costo en USD.",
                },
                "mileage_km": {
                    "type": "integer",
                    "description": "Kilometraje actual del vehículo.",
                },
                "performed_at": {
                    "type": "string",
                    "description": "Fecha del mantenimiento en formato YYYY-MM-DD. Default: hoy.",
                },
                "performed_by": {
                    "type": "string",
                    "description": "Taller o mecánico que hizo el trabajo.",
                },
                "next_at": {
                    "type": "string",
                    "description": "Fecha sugerida para el próximo mantenimiento (YYYY-MM-DD).",
                },
                "next_mileage_km": {
                    "type": "integer",
                    "description": "Kilometraje sugerido para el próximo mantenimiento.",
                },
                "file_key": {
                    "type": "string",
                    "description": "Clave del archivo en MinIO si el usuario adjuntó foto de la factura.",
                },
            },
            "required": ["vehicle_id_or_plate", "maintenance_type"],
        },
    },
}

TOOL_LIST_MAINTENANCES = {
    "type": "function",
    "function": {
        "name": "list_maintenances",
        "description": "Mostrar el historial de mantenimientos de un vehículo. Usar cuando el usuario pregunta '¿qué mantenimientos le hice al carro?', '¿cuándo fue el último cambio de aceite?', o quiere ver el historial.",
        "parameters": {
            "type": "object",
            "properties": {
                "vehicle_id_or_plate": {
                    "type": "string",
                    "description": "ID del vehículo o placa. Ej: 'PBC1234'.",
                },
            },
            "required": ["vehicle_id_or_plate"],
        },
    },
}

TOOL_DELETE_VEHICLE = {
    "type": "function",
    "function": {
        "name": "delete_vehicle",
        "description": "Eliminar un vehículo (soft delete). Usar SOLO cuando el usuario pide explícitamente 'elimina mi carro', 'borra el vehículo X', 'ya no tengo ese carro'.",
        "parameters": {
            "type": "object",
            "properties": {
                "plate": {
                    "type": "string",
                    "description": "Placa del vehículo a eliminar. Ej: 'PBC1234'.",
                },
            },
            "required": ["plate"],
        },
    },
}

TOOL_UPDATE_VEHICLE = {
    "type": "function",
    "function": {
        "name": "update_vehicle",
        "description": "Actualizar datos de un vehículo: placa, marca, modelo, año, color. Usar cuando el usuario dice 'corrige la placa', 'cambia el año de mi carro', 'mi carro es azul no rojo'.",
        "parameters": {
            "type": "object",
            "properties": {
                "plate": {
                    "type": "string",
                    "description": "Placa actual del vehículo a modificar (requerido para identificarlo).",
                },
                "new_plate": {
                    "type": "string",
                    "description": "Nueva placa si cambió.",
                },
                "brand": {
                    "type": "string",
                    "description": "Nueva marca.",
                },
                "model": {
                    "type": "string",
                    "description": "Nuevo modelo.",
                },
                "year": {
                    "type": "integer",
                    "description": "Nuevo año.",
                },
                "color": {
                    "type": "string",
                    "description": "Nuevo color.",
                },
                "notes": {
                    "type": "string",
                    "description": "Nuevas notas.",
                },
            },
            "required": ["plate"],
        },
    },
}

TOOL_SUBSCRIBE_TO_PLAN = {
    "type": "function",
    "function": {
        "name": "subscribe_to_plan",
        "description": "Iniciar suscripción a un plan de Lucho. Usar cuando el usuario dice 'suscribirme', 'contratar plan', 'pagar suscripción', 'cambiar de plan', 'elegir plan premium/familia'.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_slug": {
                    "type": "string",
                    "enum": ["basic", "premium", "family"],
                    "description": "Slug del plan: 'basic' ($4.99/mes), 'premium' ($9.99/mes), 'family' ($14.99/mes).",
                },
                "renewal": {
                    "type": "string",
                    "enum": ["monthly", "annual"],
                    "description": "Tipo de renovación. Default: 'monthly'.",
                },
            },
            "required": ["plan_slug"],
        },
    },
}

TOOL_UPDATE_BILLING_INFO = {
    "type": "function",
    "function": {
        "name": "update_billing_info",
        "description": "Guardar o actualizar datos de facturación del usuario: cédula/RUC, nombre, dirección, teléfono, correo. Usar cuando el usuario dice 'mis datos para factura', 'factura a mi nombre', 'factura a nombre de mi empresa', 'datos de facturación'.",
        "parameters": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Etiqueta: 'personal', 'empresa', o cualquier nombre para identificar este perfil.",
                },
                "full_name": {
                    "type": "string",
                    "description": "Nombre completo o Razón Social.",
                },
                "id_number": {
                    "type": "string",
                    "description": "Cédula (10 dígitos), RUC (13 dígitos), o pasaporte.",
                },
                "id_type": {
                    "type": "string",
                    "enum": ["cedula", "ruc", "pasaporte", "consumidor_final"],
                    "description": "Tipo de identificación. Default: 'cedula'.",
                },
                "email": {
                    "type": "string",
                    "description": "Correo electrónico para recibir la factura.",
                },
                "phone": {
                    "type": "string",
                    "description": "Teléfono de contacto.",
                },
                "address": {
                    "type": "string",
                    "description": "Dirección completa (obligatorio SRI). Ej: 'Av. Amazonas N24-33 y Colón, Quito'.",
                },
            },
            "required": ["full_name", "id_number", "email", "address"],
        },
    },
}

TOOL_CREATE_QUOTE = {
    "type": "function",
    "function": {
        "name": "create_quote",
        "description": "Crear una cotización/proforma para un cliente. Calcula automáticamente subtotal, IVA (tasa configurable) y total. Usar cuando el usuario dice 'cotización para...', 'proforma para...', 'presupuesto para...'.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {
                    "type": "string",
                    "description": "Nombre del cliente o razón social.",
                },
                "client_id_number": {
                    "type": "string",
                    "description": "Cédula o RUC del cliente (opcional).",
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "Descripción del ítem."},
                            "quantity": {"type": "number", "description": "Cantidad. Default: 1."},
                            "unit_price": {"type": "number", "description": "Precio unitario sin IVA."},
                        },
                        "required": ["description", "unit_price"]
                    },
                    "description": "Ítems de la cotización.",
                },
                "notes": {
                    "type": "string",
                    "description": "Notas o términos. Ej: 'Válido por 15 días', '50% anticipo'.",
                },
            },
            "required": ["client_name", "items"],
        },
    },
}

TOOL_LIST_MY_QUOTES = {
    "type": "function",
    "function": {
        "name": "list_my_quotes",
        "description": "Consultar cotizaciones emitidas. Usar cuando pregunta '¿qué cotizaciones tengo?', 'mis cotizaciones', '¿cuánto he cotizado este mes?'.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["draft", "sent", "accepted", "rejected", "expired", "all"],
                    "description": "Filtrar por estado. Default: 'all'.",
                },
                "period": {
                    "type": "string",
                    "enum": ["this_month", "last_month", "all"],
                    "description": "Período. Default: 'this_month'.",
                },
            },
            "required": [],
        },
    },
}

TOOL_SAVE_BILLING_CLIENT = {
    "type": "function",
    "function": {
        "name": "save_billing_client",
        "description": "Guardar datos de un cliente frecuente para usarlo en cotizaciones. Usar cuando el usuario dice 'guarda los datos de...', 'agrega este cliente'.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre o Razón Social."},
                "id_type": {
                    "type": "string",
                    "enum": ["cedula", "ruc", "pasaporte", "consumidor_final"],
                    "description": "Tipo de identificación.",
                },
                "id_number": {"type": "string", "description": "Cédula (10) o RUC (13)."},
                "email": {"type": "string", "description": "Correo electrónico."},
                "phone": {"type": "string", "description": "Teléfono."},
                "address": {"type": "string", "description": "Dirección."},
            },
            "required": ["name", "id_number"],
        },
    },
}

TOOL_SAVE_BILLING_PRODUCT = {
    "type": "function",
    "function": {
        "name": "save_billing_product",
        "description": "Guardar un producto o servicio en el catálogo. Usar cuando el usuario dice 'agrega a mi catálogo...', 'guarda este producto'.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre del producto/servicio."},
                "unit_price": {"type": "number", "description": "Precio unitario sin IVA."},
                "has_iva": {"type": "boolean", "description": "¿Aplica IVA? Default: true."},
                "code": {"type": "string", "description": "Código interno (opcional)."},
            },
            "required": ["name", "unit_price"],
        },
    },
}


# =============================================================================
# FINANCE TOOLS — transactions and budgets
# =============================================================================

TOOL_ADD_TRANSACTION = {
    "type": "function",
    "function": {
        "name": "add_transaction",
        "description": "Registrar un gasto o ingreso. Usar cuando el usuario dice 'gasté', 'pagué', 'compré' (expense) o 'recibí', 'cobré', 'me pagaron' (income).",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["expense", "income"],
                    "description": "'expense' si es un gasto, 'income' si es un ingreso.",
                },
                "amount": {
                    "type": "number",
                    "description": "Monto en dólares (positivo). Ej: 20.50.",
                },
                "category": {
                    "type": "string",
                    "enum": ["food", "transport", "housing", "health", "entertainment", "services",
                             "education", "clothing", "other_expense", "salary", "business", "gift",
                             "investment", "other_income"],
                    "description": "Categoría. Mapear según lo que dijo el usuario: almuerzo→food, gasolina→transport, luz→services, sueldo→salary, etc.",
                },
                "description": {
                    "type": "string",
                    "description": "Descripción corta. Ej: 'Almuerzo con cliente', 'Pago de luz mayo'.",
                },
                "transaction_date": {
                    "type": "string",
                    "description": "Fecha YYYY-MM-DD. Si no la menciona, es hoy. Si dice 'ayer', usar fecha de ayer.",
                },
                "payment_method": {
                    "type": "string",
                    "enum": ["cash", "debit", "credit", "transfer"],
                    "description": "Método de pago. Opcional.",
                },
            },
            "required": ["type", "amount", "category", "description"],
        },
    },
}

TOOL_LIST_TRANSACTIONS = {
    "type": "function",
    "function": {
        "name": "list_transactions",
        "description": "Consultar gastos e ingresos del usuario. Usar cuando pregunta '¿cuánto gasté?', '¿en qué gasté?', 'mis gastos de esta semana', 'mis ingresos'.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["expense", "income", "all"],
                    "description": "Filtrar por tipo. Default: 'all'.",
                },
                "category": {
                    "type": "string",
                    "description": "Filtrar por categoría. Opcional.",
                },
                "period": {
                    "type": "string",
                    "enum": ["today", "yesterday", "this_week", "last_week", "this_month", "last_month"],
                    "description": "Período. Default: 'this_month'.",
                },
                "group_by": {
                    "type": "string",
                    "enum": ["none", "category", "day"],
                    "description": "Agrupar resultados. Default: 'none'.",
                },
            },
            "required": [],
        },
    },
}

TOOL_GET_BALANCE = {
    "type": "function",
    "function": {
        "name": "get_balance",
        "description": "Obtener balance financiero: total de ingresos, gastos y saldo del mes. Usar cuando pregunta '¿cómo voy?', '¿cuánto tengo?', 'mi balance'.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["this_month", "last_month", "this_year"],
                    "description": "Período. Default: 'this_month'.",
                },
            },
            "required": [],
        },
    },
}

TOOL_SET_BUDGET = {
    "type": "function",
    "function": {
        "name": "set_budget",
        "description": "Configurar un presupuesto por categoría. Usar cuando dice 'ponme un presupuesto', 'mi presupuesto de comida es', 'solo quiero gastar X en Y'.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["food", "transport", "housing", "health", "entertainment", "services",
                             "education", "clothing", "other_expense"],
                    "description": "Categoría a presupuestar (solo gastos).",
                },
                "amount": {
                    "type": "number",
                    "description": "Monto máximo del presupuesto.",
                },
                "period": {
                    "type": "string",
                    "enum": ["monthly", "weekly"],
                    "description": "Período. Default: 'monthly'.",
                },
                "alert_threshold": {
                    "type": "integer",
                    "description": "Porcentaje al que alertar (ej: 80). Default: 80.",
                },
            },
            "required": ["category", "amount"],
        },
    },
}

TOOL_CHECK_BUDGET = {
    "type": "function",
    "function": {
        "name": "check_budget",
        "description": "Revisar estado de presupuestos. Usar cuando dice '¿cómo voy con el presupuesto?', '¿me pasé del presupuesto de comida?'.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Categoría específica. Si no se pasa, muestra todas.",
                },
            },
            "required": [],
        },
    },
}


# All available tools (exported for the agent loop)
ALL_TOOLS = [
    TOOL_SAVE_VEHICLE,
    TOOL_LIST_MY_VEHICLES,
    TOOL_ADD_MAINTENANCE,
    TOOL_LIST_MAINTENANCES,
    TOOL_DELETE_VEHICLE,
    TOOL_UPDATE_VEHICLE,
    TOOL_SUBSCRIBE_TO_PLAN,
    TOOL_UPDATE_BILLING_INFO,
    TOOL_CREATE_QUOTE,
    TOOL_LIST_MY_QUOTES,
    TOOL_SAVE_BILLING_CLIENT,
    TOOL_SAVE_BILLING_PRODUCT,
    TOOL_SAVE_DOCUMENT,
    TOOL_LIST_MY_DOCUMENTS,
    TOOL_SAVE_EVENT,
    TOOL_LIST_MY_EVENTS,
    TOOL_SAVE_LIST,
    TOOL_LIST_ITEMS,
    TOOL_COMPLETE_ITEM,
    TOOL_DELETE_LIST,
    TOOL_SAVE_NOTE,
    TOOL_LIST_MY_NOTES,
    TOOL_DELETE_NOTE,
    TOOL_SEARCH_DATA,
    TOOL_SEARCH_CONVERSATION,
    TOOL_ANALYZE_IMAGE,
    TOOL_GET_SUMMARY,
    TOOL_SAVE_PROJECT_TASK,
    TOOL_LIST_PROJECT_TASKS,
    TOOL_COMPLETE_PROJECT_TASK,
    TOOL_REOPEN_PROJECT_TASK,
    TOOL_ARCHIVE_PROJECT,
    TOOL_UPDATE_LAST,
    TOOL_SAVE_CONTACT,
    TOOL_LIST_CONTACTS,
    TOOL_DELETE_CONTACT,
    TOOL_CHECK_VEHICLE_INFO,
    TOOL_SEND_PHOTO,
    TOOL_WEB_SEARCH,
    TOOL_ADD_TRANSACTION,
    TOOL_LIST_TRANSACTIONS,
    TOOL_GET_BALANCE,
    TOOL_SET_BUDGET,
    TOOL_CHECK_BUDGET,
]

# Map tool names to their schemas for quick lookup
TOOL_SCHEMAS: dict[str, dict] = {
    t["function"]["name"]: t for t in ALL_TOOLS
}


# =============================================================================
# TOOL HANDLERS — deterministic Python code. LLM NEVER touches this.
# =============================================================================

async def handle_save_vehicle(session, user_id: str, args: dict) -> dict:
    """Save a vehicle to the dedicated vehicles table (max 2 per user)."""
    from datetime import date
    import uuid as uuid_mod
    from app.models.vehicle import Vehicle

    plate = (args.get("plate") or "").upper().strip().replace("-", "")
    if not plate:
        return {"success": False, "message": "Necesito la placa del vehículo."}

    user_uuid = uuid_mod.UUID(user_id)

    # ---- Enforce max vehicles per user from subscription plan features ----
    from app.models.subscription import Subscription, SubscriptionStatus
    sub_result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == user_uuid)
        .where(Subscription.status.in_([SubscriptionStatus.trial, SubscriptionStatus.active]))
    )
    sub = sub_result.scalar_one_or_none()

    max_vehicles = 2  # default
    if sub and sub.plan_ref and sub.plan_ref.features:
        max_vehicles = sub.plan_ref.features.get("max_vehicles", 2)

    count_result = await session.execute(
        select(Vehicle).where(
            Vehicle.user_id == user_uuid,
            Vehicle.deleted_at.is_(None),
        )
    )
    existing_count = len(count_result.scalars().all())
    if existing_count >= max_vehicles:
        return {
            "success": False,
            "message": (
                f"Ya tienes {existing_count} vehículo(s) registrado(s). "
                f"Tu plan permite máximo {max_vehicles}. "
                "Si quieres reemplazar uno, primero elimínalo y luego agregá el nuevo. "
                "Decime 'eliminar vehículo [placa]' y lo borro."
            ),
        }

    # ---- Check for duplicate plate ----
    dup_result = await session.execute(
        select(Vehicle).where(
            Vehicle.user_id == user_uuid,
            Vehicle.plate == plate,
            Vehicle.deleted_at.is_(None),
        )
    )
    if dup_result.scalar_one_or_none():
        return {
            "success": False,
            "message": f"El vehículo con placa {plate} ya está registrado. Si quieres actualizarlo, dime 'actualizar vehículo {plate}'.",
        }

    # ---- Compute vehicle rules (pico y placa, matriculación) ----
    today = date.today()
    last_digit = None
    pyp_days = ""
    next_matric = None
    try:
        rules = evaluate_vehicle_rules(plate, None, today)
        last_digit = rules["last_digit"]
        pyp_days = rules["pico_y_placa_days"]
        next_matric = date.fromisoformat(rules["next_matriculation"])
    except Exception as exc:
        logger.warning("Could not compute vehicle rules for %s: %s", plate, exc)

    # ---- Create vehicle ----
    vehicle = Vehicle(
        user_id=user_uuid,
        plate=plate,
        brand=args.get("brand"),
        model=args.get("model"),
        year=args.get("year"),
        last_digit=last_digit,
        pico_y_placa_days=pyp_days,
        next_matriculation=next_matric,
        notes=args.get("notes"),
    )
    session.add(vehicle)
    await session.flush()

    # ---- Build response ----
    brand_model = ""
    if args.get("brand") and args.get("model"):
        brand_model = f"{args['brand']} {args['model']} "
    elif args.get("brand"):
        brand_model = f"{args['brand']} "

    pyp_info = f"\n• Pico y placa: {pyp_days}" if pyp_days else ""
    matric_info = f"\n• Próxima matriculación: {next_matric}" if next_matric else ""

    return {
        "success": True,
        "message": f"Vehículo {plate} guardado.",
        "vehicle": {
            "id": str(vehicle.id),
            "plate": plate,
            "brand": args.get("brand"),
            "model": args.get("model"),
            "year": args.get("year"),
            "pico_y_placa_days": pyp_days,
            "next_matriculation": str(next_matric) if next_matric else None,
            "last_digit": last_digit,
        },
    }


async def handle_save_document(session, user_id: str, args: dict) -> dict:
    """Save a personal document."""
    import uuid

    doc_type = (args.get("document_type") or "otro").lower().strip()
    name = (args.get("name") or "documento").strip()
    document_number = args.get("document_number")
    expiry_date = args.get("expiry_date")
    entity_name = args.get("entity_name")
    tags = args.get("tags")
    file_key = args.get("file_key")

    try:
        doc = await persist_document(
            session=session,
            user_id=uuid.UUID(user_id),
            document_type=doc_type,
            name=name,
            document_number=document_number,
            expiry_date=expiry_date,
            entity_name=entity_name,
            notes=args.get("notes"),
            tags=tags,
            file_key=file_key,
        )
        expiry_msg = f", vence {expiry_date}" if expiry_date else ""
        has_photo = " (con foto)" if file_key else ""
        return {
            "success": True,
            "message": f"Documento '{name}' guardado{expiry_msg}{has_photo}.",
            "file_key": file_key,
            "document_id": str(doc.id),
        }
    except Exception as exc:
        logger.exception("Failed to save document: %s", exc)
        return {"success": False, "message": "No pude guardar el documento."}


async def handle_list_my_documents(session, user_id: str, args: dict) -> dict:
    """List user documents with optional filters by type and status."""
    import uuid as uuid_mod
    from datetime import date, timedelta
    from sqlalchemy import select
    from app.models.document import Document, DocumentType

    uid = uuid_mod.UUID(user_id)
    doc_type = args.get("document_type")
    status = args.get("status", "all")

    # Build base query
    query = select(Document).where(
        Document.user_id == uid,
        Document.deleted_at.is_(None),
    )

    # Filter by document type
    if doc_type:
        try:
            dt_enum = DocumentType(doc_type.lower().strip())
            query = query.where(Document.document_type == dt_enum)
        except ValueError:
            pass  # Invalid type, ignore filter silently

    result = await session.execute(query.order_by(Document.created_at.desc()))
    docs = result.scalars().all()

    if not docs:
        type_msg = f" de tipo '{doc_type}'" if doc_type else ""
        return {
            "success": True,
            "message": f"No tienes documentos{type_msg} guardados todavía. Mándame una foto o dime 'guardame mi cédula' y lo archivo.",
            "documents": [],
            "total": 0,
        }

    today = date.today()
    days_30 = today + timedelta(days=30)

    # Type label map for friendly display
    type_labels = {
        "cedula": "🆔 Cédula",
        "pasaporte": "🛂 Pasaporte",
        "licencia": "🚗 Licencia",
        "soat": "🚗 SOAT",
        "seguro": "🛡️ Seguro",
        "factura": "📄 Factura",
        "garantia": "🔧 Garantía",
        "certificado": "📝 Certificado",
        "escritura": "📋 Escritura",
        "contrato": "🏦 Contrato",
        "tarjeta": "💳 Tarjeta",
        "otro": "📸 Otro",
    }

    # Apply status filter and build result list
    filtered = []
    for doc in docs:
        # Determine effective status from expiry_date
        if doc.expiry_date:
            if doc.expiry_date < today:
                effective_status = "expired"
            elif doc.expiry_date <= days_30:
                effective_status = "expiring_soon"
            else:
                effective_status = "active"
        else:
            effective_status = "active"

        # Apply optional status filter
        if status == "expiring_soon" and effective_status != "expiring_soon":
            continue
        if status == "expired" and effective_status != "expired":
            continue
        if status == "active" and effective_status != "active":
            continue

        dt_value = doc.document_type.value if doc.document_type else "otro"
        item = {
            "id": str(doc.id),
            "document_type": dt_value,
            "type_label": type_labels.get(dt_value, "📸 Otro"),
            "name": doc.name,
            "document_number": doc.document_number,
            "expiry_date": str(doc.expiry_date) if doc.expiry_date else None,
            "entity_name": doc.entity_name,
            "status": effective_status,
            "notes": doc.notes,
        }
        if doc.file_key:
            item["file_key"] = doc.file_key
        if doc.file_keys:
            item["file_keys"] = doc.file_keys
        filtered.append(item)

    if not filtered:
        status_labels = {
            "expiring_soon": "que venzan pronto",
            "expired": "vencidos",
            "active": "activos",
        }
        status_msg = status_labels.get(status, "")
        type_msg = f" de tipo '{doc_type}'" if doc_type else ""
        return {
            "success": True,
            "message": f"No tienes documentos{type_msg} {status_msg}.".strip(),
            "documents": [],
            "total": 0,
        }

    # Count by effective status for summary
    counts = {"active": 0, "expiring_soon": 0, "expired": 0}
    for d in filtered:
        counts[d["status"]] += 1

    return {
        "success": True,
        "message": f"Tenés {len(filtered)} documento(s).",
        "documents": filtered,
        "total": len(filtered),
        "counts": counts,
    }


async def handle_save_event(session, user_id: str, args: dict) -> dict:
    """Save an event/reminder."""
    import uuid

    title = (args.get("title") or "evento").strip()
    target_date = args.get("target_date", "")
    recurrence = args.get("recurrence", "none")
    file_key = args.get("file_key", "")

    if not target_date:
        return {"success": False, "message": "Necesito saber la fecha del evento."}

    recurrence_rule = None
    if recurrence and recurrence != "none":
        recurrence_rule = {"freq": recurrence, "interval": 1}

    description = args.get("description") or ""
    if file_key:
        description = f"{description}\n[📸 foto: {file_key}]".strip()

    try:
        event = await persist_event(
            session=session,
            user_id=uuid.UUID(user_id),
            title=title,
            target_date=target_date,
            description=description,
            certainty="certain",
            recurrence_rule=recurrence_rule,
        )

        # Schedule ad-hoc reminder if the event has a specific time (not just a date)
        from app.services.scheduler import schedule_event_reminder
        if event.target_date.hour != 0 or event.target_date.minute != 0:
            schedule_event_reminder(str(event.id), event.target_date)

        recur_msg = f", se repite {recurrence}" if recurrence_rule else ""
        photo_msg = " (con foto adjunta)" if file_key else ""
        return {
            "success": True,
            "message": f"Evento '{title}' agendado para {target_date}{recur_msg}{photo_msg}. Te recordaré antes.",
            "event_id": str(event.id),
            "target_date": str(event.target_date),
            "file_key": file_key if file_key else None,
        }
    except Exception as exc:
        logger.exception("Failed to save event: %s", exc)
        return {"success": False, "message": "No pude guardar el evento."}


async def handle_list_my_events(session, user_id: str, args: dict) -> dict:
    """List user events with status and period filters."""
    import uuid as uuid_mod
    from datetime import date, datetime, timedelta
    from sqlalchemy import select
    from app.models.event import Event, EventStatus

    uid = uuid_mod.UUID(user_id)
    status_filter = args.get("status", "upcoming")
    period = args.get("period", "all")

    today = date.today()
    now = datetime.combine(today, datetime.min.time())

    # Determine date range
    if period == "today":
        start = now
        end = datetime.combine(today, datetime.max.time())
    elif period == "tomorrow":
        tomorrow = today + timedelta(days=1)
        start = datetime.combine(tomorrow, datetime.min.time())
        end = datetime.combine(tomorrow, datetime.max.time())
    elif period == "this_week":
        start = now
        end_of_week = today + timedelta(days=(6 - today.weekday()))
        end = datetime.combine(end_of_week, datetime.max.time())
    elif period == "next_week":
        next_monday = today + timedelta(days=(7 - today.weekday()))
        start = datetime.combine(next_monday, datetime.min.time())
        end = datetime.combine(next_monday + timedelta(days=6), datetime.max.time())
    elif period == "this_month":
        start = now
        if today.month == 12:
            end_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)
        end = datetime.combine(end_of_month, datetime.max.time())
    else:  # all — next 90 days
        start = now
        end = datetime.combine(today + timedelta(days=90), datetime.max.time())

    # Build query
    query = select(Event).where(Event.user_id == uid)

    if status_filter == "all":
        query = query.where(Event.target_date >= start, Event.target_date <= end)
    elif status_filter == "upcoming":
        query = query.where(
            Event.status == EventStatus.upcoming,
            Event.target_date >= start,
            Event.target_date <= end,
        )
    else:
        try:
            es = EventStatus(status_filter)
            query = query.where(Event.status == es)
        except ValueError:
            query = query.where(Event.status == EventStatus.upcoming)

    result = await session.execute(query.order_by(Event.target_date.asc()).limit(30))
    events = result.scalars().all()

    if not events:
        status_msg = {
            "upcoming": "próximos",
            "done": "completados",
            "cancelled": "cancelados",
            "overdue": "vencidos",
            "all": "",
        }.get(status_filter, "")
        return {"success": True, "message": f"No tienes eventos {status_msg}.".strip(), "events": [], "total": 0}

    event_list = []
    for e in events:
        days_until = (e.target_date.date() - today).days if e.target_date else None
        event_list.append({
            "id": str(e.id),
            "title": e.title,
            "target_date": str(e.target_date),
            "description": e.description,
            "status": e.status.value if e.status else "upcoming",
            "recurrence": e.recurrence_rule,
            "days_until": days_until,
        })

    return {
        "success": True,
        "message": f"Tenés {len(events)} evento(s).",
        "events": event_list,
        "total": len(events),
    }


async def handle_save_list(session, user_id: str, args: dict) -> dict:
    """Save items to a list."""
    import uuid

    list_name = (args.get("list_name") or "general").strip()
    items = args.get("items") or []

    if not items:
        return {"success": False, "message": "Necesito al menos un ítem para la lista."}

    try:
        saved = await persist_list_items(
            session=session,
            user_id=uuid.UUID(user_id),
            list_name=list_name,
            items=items,
            quantity=args.get("quantity"),
        )
        created = len([i for i in saved if i.id]) if saved else 0
        total = len(items)
        if created < total:
            skipped = total - created
            return {
                "success": True,
                "message": f"{created} ítem(s) agregado(s) a '{list_name}' ({skipped} ya existían).",
                "count": created,
                "skipped": skipped,
                "list_name": list_name,
            }
        return {
            "success": True,
            "message": f"{created} ítem(s) agregado(s) a '{list_name}'.",
            "count": created,
            "list_name": list_name,
        }
    except Exception as exc:
        logger.exception("Failed to save list items: %s", exc)
        return {"success": False, "message": "No pude guardar los ítems."}


async def handle_list_items(session, user_id: str, args: dict) -> dict:
    """List items from one list or all lists, with status filter."""
    import uuid as uuid_mod
    from sqlalchemy import select
    from app.models.list import List, ListItem, ItemStatus

    uid = uuid_mod.UUID(user_id)
    list_name = args.get("list_name")
    status = args.get("status", "pending")

    # ---- Query lists -------
    list_query = select(List).where(List.user_id == uid)
    if list_name:
        list_query = list_query.where(List.name == list_name)

    list_result = await session.execute(list_query.order_by(List.name))
    lists = list_result.scalars().all()

    if not lists:
        msg = f"No tienes la lista '{list_name}'." if list_name else "No tienes listas todavía. Mándame 'lista de compras: leche, pan' y te la creo."
        return {"success": True, "message": msg, "lists": [], "total": 0}

    # ---- Query items for those lists -------
    list_ids = [lst.id for lst in lists]
    items_query = select(ListItem).where(ListItem.list_id.in_(list_ids))
    if status != "all":
        try:
            items_query = items_query.where(ListItem.status == ItemStatus(status))
        except ValueError:
            pass

    items_result = await session.execute(
        items_query.order_by(ListItem.created_at.asc())
    )
    all_items = items_result.scalars().all()

    if not all_items:
        status_msg = "pendientes" if status == "pending" else ("completados" if status == "done" else "")
        name_msg = f" en '{list_name}'" if list_name else ""
        return {
            "success": True,
            "message": f"No hay ítems {status_msg}{name_msg}.".strip(),
            "lists": [],
            "total": 0,
        }

    # ---- Group items by list -------
    from collections import defaultdict
    grouped = defaultdict(list)
    for item in all_items:
        lst_name = next((l.name for l in lists if l.id == item.list_id), "?")
        grouped[lst_name].append({
            "id": str(item.id),
            "content": item.content,
            "quantity": item.quantity,
            "status": item.status.value if item.status else "pending",
            "created_at": str(item.created_at),
        })

    result_lists = [
        {"list_name": name, "items": items, "count": len(items)}
        for name, items in grouped.items()
    ]

    total = sum(l["count"] for l in result_lists)
    return {
        "success": True,
        "message": f"Tenés {total} ítem(s) en {len(result_lists)} lista(s).",
        "lists": result_lists,
        "total": total,
    }


async def handle_complete_item(session, user_id: str, args: dict) -> dict:
    """Mark items as done by content match, optionally across all lists."""
    import uuid as uuid_mod
    from datetime import datetime, timezone
    from sqlalchemy import select, update
    from app.models.list import List, ListItem, ItemStatus

    uid = uuid_mod.UUID(user_id)
    list_name = args.get("list_name")
    item_texts = args.get("items") or []
    mark_all = args.get("mark_all", False)

    if not item_texts and not mark_all:
        return {"success": False, "message": "¿Qué ítems quieres marcar como completados?"}

    # ---- Find target lists -------
    list_query = select(List).where(List.user_id == uid)
    if list_name:
        list_query = list_query.where(List.name == list_name)
    list_result = await session.execute(list_query)
    lists = list_result.scalars().all()

    if not lists:
        msg = f"No tienes la lista '{list_name}'." if list_name else "No tienes listas."
        return {"success": False, "message": msg}

    list_ids = [lst.id for lst in lists]

    # ---- Find matching items -------
    now = datetime.now(timezone.utc)

    if mark_all:
        # Mark all pending items in these lists as done
        items_query = select(ListItem).where(
            ListItem.list_id.in_(list_ids),
            ListItem.status == ItemStatus.pending,
        )
        items_result = await session.execute(items_query)
        matched = items_result.scalars().all()
    else:
        # Match by content (partial, case-insensitive)
        matched = []
        items_query = select(ListItem).where(
            ListItem.list_id.in_(list_ids),
            ListItem.status == ItemStatus.pending,
        )
        items_result = await session.execute(items_query)
        pending_items = items_result.scalars().all()

        for item_text in item_texts:
            text_lower = item_text.strip().lower()
            for pi in pending_items:
                if pi.id not in [m.id for m in matched] and text_lower in pi.content.lower():
                    matched.append(pi)
                    break

    if not matched:
        return {"success": True, "message": "No encontré ítems pendientes que coincidan. ¿Ya estaban completados?"}

    # ---- Mark as done -------
    matched_ids = [m.id for m in matched]
    await session.execute(
        update(ListItem)
        .where(ListItem.id.in_(matched_ids))
        .values(status=ItemStatus.done, completed_at=now)
    )
    await session.flush()

    # Build friendly names
    completed_names = [m.content for m in matched]
    names_str = ", ".join(completed_names[:5])
    if len(completed_names) > 5:
        names_str += f" y {len(completed_names) - 5} más"

    return {
        "success": True,
        "message": f"¡Listo! {len(matched)} ítem(s) completado(s): {names_str}.",
        "completed": len(matched),
        "items": completed_names,
    }


async def handle_delete_list(session, user_id: str, args: dict) -> dict:
    """Delete an entire list and all its items."""
    import uuid as uuid_mod
    from sqlalchemy import select, delete
    from app.models.list import List, ListItem

    uid = uuid_mod.UUID(user_id)
    list_name = (args.get("list_name") or "").strip()

    if not list_name:
        return {"success": False, "message": "¿Qué lista quieres eliminar?"}

    # Find the list
    result = await session.execute(
        select(List).where(List.user_id == uid, List.name == list_name)
    )
    lst = result.scalar_one_or_none()

    if not lst:
        return {"success": True, "message": f"No tienes una lista llamada '{list_name}'."}

    # Count items before deleting
    count_result = await session.execute(
        select(ListItem).where(ListItem.list_id == lst.id)
    )
    item_count = len(count_result.scalars().all())

    # Delete items first (cascade should handle this, but be explicit)
    await session.execute(delete(ListItem).where(ListItem.list_id == lst.id))
    await session.delete(lst)
    await session.flush()

    return {
        "success": True,
        "message": f"Lista '{list_name}' eliminada con {item_count} ítem(s).",
        "list_name": list_name,
        "deleted_items": item_count,
    }


async def handle_save_note(session, user_id: str, args: dict) -> dict:
    """Save a note."""
    import uuid

    topic = (args.get("topic") or "general").strip()
    content = (args.get("content") or "").strip()
    file_key = args.get("file_key")

    if not content:
        return {"success": False, "message": "Necesito el contenido de la nota."}

    try:
        note = await persist_note(
            session=session,
            user_id=uuid.UUID(user_id),
            topic_name=topic,
            content=content,
            file_key=file_key,
        )
        has_photo = " (con foto)" if file_key else ""
        return {
            "success": True,
            "message": f"Nota guardada en '{topic}'{has_photo}.",
            "note_id": str(note.id),
            "topic": topic,
            "file_key": file_key,
        }
    except Exception as exc:
        logger.exception("Failed to save note: %s", exc)
        return {"success": False, "message": "No pude guardar la nota."}


async def handle_list_my_notes(session, user_id: str, args: dict) -> dict:
    """List user notes grouped by topic."""
    import uuid as uuid_mod
    from sqlalchemy import select
    from app.models.topic import Topic, Note

    uid = uuid_mod.UUID(user_id)
    topic_filter = args.get("topic")

    # ---- Query topics -------
    topic_query = select(Topic).where(Topic.user_id == uid)
    if topic_filter:
        topic_query = topic_query.where(Topic.name == topic_filter)

    topic_result = await session.execute(topic_query.order_by(Topic.name))
    topics = topic_result.scalars().all()

    if not topics:
        msg = f"No tienes notas en '{topic_filter}'." if topic_filter else "No tienes notas guardadas todavía. Mándame 'anota: ...' y te la guardo."
        return {"success": True, "message": msg, "topics": [], "total": 0}

    # ---- Query notes for those topics -------
    topic_ids = [t.id for t in topics]
    notes_result = await session.execute(
        select(Note)
        .where(Note.topic_id.in_(topic_ids))
        .order_by(Note.created_at.desc())
        .limit(50)
    )
    all_notes = notes_result.scalars().all()

    if not all_notes:
        msg = f"El tema '{topic_filter}' no tiene notas." if topic_filter else "No tienes notas guardadas."
        return {"success": True, "message": msg, "topics": [], "total": 0}

    # ---- Group notes by topic -------
    from collections import defaultdict
    grouped = defaultdict(list)
    for note in all_notes:
        topic_name = next((t.name for t in topics if t.id == note.topic_id), "?")
        grouped[topic_name].append({
            "id": str(note.id),
            "content": note.content[:200],
            "created_at": str(note.created_at),
        })

    result_topics = [
        {"topic": name, "notes": items, "count": len(items)}
        for name, items in grouped.items()
    ]

    total = sum(t["count"] for t in result_topics)
    return {
        "success": True,
        "message": f"Tenés {total} nota(s) en {len(result_topics)} tema(s).",
        "topics": result_topics,
        "total": total,
    }


async def handle_delete_note(session, user_id: str, args: dict) -> dict:
    """Delete a note by topic + content search."""
    import uuid as uuid_mod
    from sqlalchemy import select, delete
    from app.models.topic import Topic, Note

    uid = uuid_mod.UUID(user_id)
    topic_name = (args.get("topic") or "").strip()
    search = (args.get("search") or "").strip()

    if not topic_name or not search:
        return {"success": False, "message": "Necesito saber el tema y qué nota eliminar."}

    # Find the topic
    topic_result = await session.execute(
        select(Topic).where(Topic.user_id == uid, Topic.name == topic_name)
    )
    topic = topic_result.scalar_one_or_none()
    if not topic:
        return {"success": True, "message": f"No tienes el tema '{topic_name}'."}

    # Find matching notes
    notes_result = await session.execute(
        select(Note).where(
            Note.topic_id == topic.id,
            Note.content.ilike(f"%{search}%")
        ).limit(5)
    )
    matches = notes_result.scalars().all()

    if not matches:
        return {"success": True, "message": f"No encontré notas que coincidan con '{search}' en '{topic_name}'."}

    # Delete matches
    ids_to_delete = [n.id for n in matches]
    await session.execute(delete(Note).where(Note.id.in_(ids_to_delete)))
    await session.flush()

    names_str = ", ".join([n.content[:50] for n in matches])
    return {
        "success": True,
        "message": f"Eliminé {len(matches)} nota(s) de '{topic_name}': {names_str}.",
        "deleted": len(matches),
    }


async def handle_search_data(session, user_id: str, args: dict) -> dict:
    """Search all user data."""
    import uuid

    query = (args.get("query") or "").strip()
    search_type = (args.get("search_type") or "all").strip()

    if not query:
        return {"success": False, "message": "¿Qué quieres que busque?", "results": []}

    uid = uuid.UUID(user_id)
    results_parts: list[str] = []
    found_items: list[dict] = []

    # ---- Vehicles ----
    if search_type in ("vehicles", "all"):
        from sqlalchemy import select
        from app.models.vehicle import Vehicle
        result = await session.execute(
            select(Vehicle).where(
                Vehicle.user_id == uid,
                Vehicle.deleted_at.is_(None),
            )
        )
        vehicles = result.scalars().all()
        if vehicles:
            for v in vehicles:
                plate = v.plate or "?"
                pyp = v.pico_y_placa_days or ""
                matric = v.next_matriculation.isoformat() if v.next_matriculation else ""
                lines = [f"🚗 {plate} — {v.brand or ''} {v.model or ''}".strip()]
                if pyp:
                    lines.append(f"   Pico y placa: {pyp}")
                if matric:
                    lines.append(f"   Matriculación: {matric}")
                results_parts.append("\n".join(lines))
                found_items.append({"type": "vehicle", "plate": plate, "name": f"{v.brand or ''} {v.model or ''}".strip()})

    # ---- Documents ----
    if search_type in ("all",):
        from sqlalchemy import select
        from app.models.document import Document
        result = await session.execute(
            select(Document).where(
                Document.user_id == uid,
                Document.deleted_at.is_(None),
            )
        )
        docs = result.scalars().all()
        if docs:
            for d in docs:
                doc_type_label = d.document_type.value if d.document_type else "documento"
                lines = [f"📄 {d.name} ({doc_type_label})"]
                if d.expiry_date:
                    lines.append(f"   Vence: {d.expiry_date}")
                if d.file_key:
                    lines.append(f"   📸 foto: {d.file_key}")
                results_parts.append("\n".join(lines))
                item = {"type": "document", "document_type": doc_type_label, "name": d.name}
                if d.file_key:
                    item["file_key"] = d.file_key
                found_items.append(item)

    # ---- Pending items ----
    if search_type in ("pending", "all"):
        pending = await list_pending_items(session, uid)
        if pending:
            lines = ["📝 Pendientes:"]
            for p in pending[:10]:
                lines.append(f"   • [{p['list']}] {p['content']}")
                found_items.append({"type": "pending", "list": p["list"], "content": p["content"]})
            results_parts.append("\n".join(lines))

    # ---- Deadlines ----
    if search_type in ("deadlines", "all"):
        deadlines = await upcoming_deadlines(session, uid, days_ahead=90)
        if deadlines:
            lines = ["📅 Próximos vencimientos:"]
            for d in deadlines[:8]:
                emoji = "🔴" if d["days_left"] <= 7 else "🟡" if d["days_left"] <= 30 else "🟢"
                lines.append(f"   {emoji} {d['title']}: {d['target_date']} ({d['days_left']} días)")
                found_items.append({"type": "deadline", "title": d["title"], "date": d["target_date"], "days_left": d["days_left"]})
            results_parts.append("\n".join(lines))

    # ---- Text search (notes, lists) ----
    if search_type in ("notes", "all") and len(query) > 2:
        text_results = await search_by_text(session, uid, query, limit=5)
        if text_results:
            lines = ["💡 Encontrado:"]
            for t in text_results:
                preview = t["text"][:120]
                lines.append(f"   [{t['source']}] {preview}")
                found_items.append({"type": t["source"], "text": t["text"][:200]})
            results_parts.append("\n".join(lines))

    # ---- Semantic search ----
    if search_type == "all" and len(query) > 3:
        try:
            embedding = await generate_embedding(query)
            if embedding:
                semantic_results = await semantic_search(session, uid, embedding, top_k=5)
                if semantic_results:
                    for sr in semantic_results:
                        found_items.append({
                            "type": f"semantic_{sr['source']}",
                            "text": sr["text"][:200],
                            "similarity": sr["similarity"],
                        })
        except Exception as exc:
            logger.warning("Semantic search failed: %s", exc)

    if not found_items:
        return {
            "success": True,
            "message": "No encontré nada sobre eso. ¿Querés que lo guarde?",
            "results": [],
            "raw_data": "",
        }

    return {
        "success": True,
        "message": f"Encontré {len(found_items)} resultado(s).",
        "results": found_items,
        "raw_data": "\n\n".join(results_parts),
    }


async def handle_get_summary(session, user_id: str, args: dict) -> dict:
    """Get a quick summary of everything."""
    # Reuse search with type='all' but with an empty query approach
    return await handle_search_data(
        session, user_id,
        {"query": "resumen", "search_type": "all"}
    )


async def handle_update_last(session, user_id: str, args: dict) -> dict:
    """Update the last entity the user created."""
    import uuid
    from sqlalchemy import select, desc

    entity_type = (args.get("entity_type") or "").strip()
    field = (args.get("field") or "").strip()
    new_value = (args.get("new_value") or "").strip()

    if not entity_type or not field:
        return {"success": False, "message": "No sé qué corregir. ¿Me decís qué dato cambiar?"}

    uid = uuid.UUID(user_id)

    # Map entity types to models and their most recent query
    match entity_type:
        case "event":
            from app.models.event import Event
            result = await session.execute(
                select(Event).where(Event.user_id == uid).order_by(desc(Event.created_at)).limit(1)
            )
            entity = result.scalar_one_or_none()
            label = entity.title if entity else "evento"
        case "note":
            from app.models.topic import Note
            result = await session.execute(
                select(Note).join(Note.topic).where(Note.topic.has(user_id=uid)).order_by(desc(Note.created_at)).limit(1)
            )
            entity = result.scalar_one_or_none()
            label = "nota"
        case "list":
            from app.models.list import ListItem
            result = await session.execute(
                select(ListItem).join(ListItem.list).where(ListItem.list.has(user_id=uid)).order_by(desc(ListItem.created_at)).limit(1)
            )
            entity = result.scalar_one_or_none()
            label = "ítem"
        case "document":
            from app.models.document import Document
            result = await session.execute(
                select(Document).where(Document.user_id == uid, Document.deleted_at.is_(None)).order_by(desc(Document.created_at)).limit(1)
            )
            entity = result.scalar_one_or_none()
            label = entity.name if entity else "documento"
        case _:
            return {"success": False, "message": "No encontré qué corregir. ¿Me das más detalles?"}

    if not entity:
        return {"success": False, "message": "No encontré nada reciente para corregir."}

    if not hasattr(entity, field):
        return {"success": False, "message": f"El campo '{field}' no existe en {label}."}

    try:
        old_val = getattr(entity, field)
        setattr(entity, field, new_value)
        await session.flush()
        return {
            "success": True,
            "message": f"Corregido: {field} de '{old_val}' a '{new_value}' en {label}.",
        }
    except Exception as exc:
        logger.exception("Failed to update entity: %s", exc)
        return {"success": False, "message": "No pude hacer la corrección."}


async def handle_check_vehicle_info(session, user_id: str, args: dict) -> dict:
    """Query external API for vehicle info (SRI, matriculation, fines)."""
    import httpx
    from app.config import settings

    plate = (args.get("plate") or "").upper().strip().replace("-", "")
    if not plate:
        return {"success": False, "message": "Necesito la placa para consultar."}

    url = f"{settings.VEHICLE_INFO_API_URL}{plate}"
    headers = {"Authorization": f"Bearer {settings.VEHICLE_INFO_API_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Vehicle API HTTP error for %s: %s", plate, exc)
        return {"success": False, "message": f"El servicio de consulta no está disponible. Intentá más tarde."}
    except Exception as exc:
        logger.exception("Vehicle API error for %s: %s", plate, exc)
        return {"success": False, "message": "No pude consultar la información del vehículo."}

    if not data.get("successful"):
        return {"success": False, "message": f"No encontré información para la placa {plate}. ¿Está bien escrita?"}

    info = data.get("data", {})

    # ---- Parse vehicle data ----
    web = info.get("infoWeb", {}).get("data", {})
    sri = info.get("infoSri", {}).get("datosBase", {})
    multas_rows = info.get("multasAnt", {}).get("rows", [])
    propietario = info.get("propietario", {}).get("data", {})

    vehicle_info = {
        "plate": web.get("licensePlate") or sri.get("numeroPlaca") or plate,
        "brand": web.get("brand") or sri.get("descripcionMarca", ""),
        "model": web.get("model") or sri.get("descripcionModelo", ""),
        "year": web.get("modelYear") or sri.get("anioAuto", ""),
        "engine_cc": web.get("engineCapacity") or sri.get("cilindraje", ""),
        "vehicle_class": web.get("vehicleClass", ""),
        "service_type": web.get("serviceType", ""),
        "status": web.get("vehicleStatus", ""),
        "canton": web.get("registrationCanton", ""),
        "purchase_date": web.get("purchaseDate", ""),
        "last_registration": web.get("lastRegistrationDate", ""),
        "registration_expiry": web.get("registrationExpiryDate", ""),
        "last_payment_year": web.get("lastPaymentYear") or sri.get("ultimoAnioPagado", ""),
        "last_inspection": web.get("inspectionDate", ""),
        "country": sri.get("descripcionPais", "ECUADOR"),
    }

    # ---- Parse fines ----
    fines = []
    for m in multas_rows:
        cells = m.get("cell", [])
        if len(cells) >= 10:
            fines.append({
                "id": cells[1] if len(cells) > 1 else "?",
                "entity": cells[2] if len(cells) > 2 else "?",
                "date": (cells[6][:10] if len(cells) > 6 and cells[6] else "?"),
                "description": cells[10] if len(cells) > 10 else "Multa de tránsito",
                "status": cells[12] if len(cells) > 12 else "pendiente",
            })

    return {
        "success": True,
        "vehicle": vehicle_info,
        "fines_count": len(fines),
        "fines": fines,
    }


async def handle_search_conversation(session, user_id: str, args: dict) -> dict:
    """Search the user's message history for past conversations."""
    import uuid as uuid_mod
    from sqlalchemy import select, desc, or_, String, cast
    from app.models.message import Message

    query = (args.get("query") or "").strip()
    limit = min(int(args.get("limit") or 5), 15)

    if not query:
        return {"success": False, "message": "¿Qué quieres que busque en el historial?"}

    uid = uuid_mod.UUID(user_id)
    pattern = f"%{query}%"

    result = await session.execute(
        select(Message)
        .where(
            Message.user_id == uid,
            or_(
                Message.text.ilike(pattern),
                cast(Message.extraction_result, String).ilike(pattern),
            ),
        )
        .order_by(desc(Message.received_at))
        .limit(limit)
    )

    messages = list(result.scalars().all())

    if not messages:
        return {
            "success": True,
            "message": f"No encontré nada sobre '{query}' en nuestro historial.",
            "found": [],
        }

    found = []
    for m in messages:
        agent_reply = ""
        if m.extraction_result and isinstance(m.extraction_result, dict):
            agent_reply = m.extraction_result.get("agent_response", "")[:200]
        found.append({
            "date": m.received_at.strftime("%Y-%m-%d %H:%M") if m.received_at else "?",
            "user_said": (m.text or "")[:200],
            "lucho_replied": agent_reply,
        })

    return {
        "success": True,
        "message": f"Encontré {len(found)} mensaje(s) sobre '{query}'.",
        "found": found,
    }


async def handle_analyze_image(session, user_id: str, args: dict) -> dict:
    """Download image from MinIO and extract structured data with DeepSeek Vision."""
    from app.services import minio as minio_svc
    from app.services.vision import extract_document_data

    file_key = (args.get("file_key") or "").strip()
    hint = (args.get("hint") or "").strip()

    if not file_key:
        return {"success": False, "message": "No encuentro la foto. ¿Podés reenviarla?"}

    # Download from MinIO
    try:
        image_bytes = await minio_svc.download_file(file_key)
        if not image_bytes:
            return {"success": False, "message": "No pude acceder a la imagen. ¿Está bien guardada?"}
    except Exception as exc:
        logger.exception("MinIO download failed: %s", exc)
        return {"success": False, "message": "No pude descargar la imagen."}

    # Extract with DeepSeek Vision
    try:
        extracted = await extract_document_data(image_bytes)
    except Exception as exc:
        logger.exception("OCR extraction failed: %s", exc)
        return {"success": False, "message": "No pude leer el documento. ¿Está bien enfocado?"}

    if not extracted:
        return {"success": False, "message": "No pude extraer información de la imagen. ¿Podés describirla?"}

    doc_type = extracted.get("document_type", "documento")

    return {
        "success": True,
        "document_type": doc_type,
        "extracted": extracted,
        "file_key": file_key,
        "_save_hint": f"AHORA preguntale al usuario si quiere guardar este documento como '{doc_type}'. NO lo guardes sin confirmación. Si el usuario confirma, llamá a save_document con document_type='{doc_type}', name='{extracted.get('title', doc_type)}', file_key='{file_key}', y los datos extraídos.",
    }


async def handle_save_project_task(session, user_id: str, args: dict) -> dict:
    """Save a task to a project."""
    import uuid
    from app.services.persistence import persist_project_task

    project_name = (args.get("project_name") or "general").strip()
    content = (args.get("content") or "").strip()

    if not content:
        return {"success": False, "message": "¿Qué tarea quieres agregar al proyecto?"}

    due_date = None
    if args.get("due_date"):
        try:
            from datetime import date as dt_date
            due_date = dt_date.fromisoformat(args["due_date"])
        except (ValueError, TypeError):
            pass

    try:
        task = await persist_project_task(
            session=session,
            user_id=uuid.UUID(user_id),
            project_name=project_name,
            content=content,
            due_date=due_date,
        )
        due_msg = f" para {args['due_date']}" if due_date else ""
        return {
            "success": True,
            "message": f"Tarea '{content[:60]}' agregada al proyecto '{project_name}'{due_msg}.",
            "task_id": str(task.id),
            "project_name": project_name,
        }
    except Exception as exc:
        logger.exception("Failed to save project task: %s", exc)
        return {"success": False, "message": "No pude guardar la tarea."}


async def handle_list_project_tasks(session, user_id: str, args: dict) -> dict:
    """List tasks for a project or all projects."""
    import uuid
    from sqlalchemy import select
    from app.models.project import Project, ProjectTask, TaskStatus

    uid = uuid.UUID(user_id)
    project_name = (args.get("project_name") or "").strip()
    status_filter = (args.get("status") or "all").strip()

    # Query projects
    query = select(Project).where(Project.user_id == uid, Project.status == "active")
    if project_name:
        query = query.where(Project.name == project_name)
    result = await session.execute(query.order_by(Project.name))
    projects = result.scalars().all()

    if not projects:
        return {"success": True, "message": "No tienes proyectos todavía. Decime 'crear proyecto X' y empezamos.", "projects": []}

    output = []
    for proj in projects:
        task_query = select(ProjectTask).where(ProjectTask.project_id == proj.id)
        if status_filter == "pending":
            task_query = task_query.where(ProjectTask.status == TaskStatus.pending)
        elif status_filter == "done":
            task_query = task_query.where(ProjectTask.status == TaskStatus.done)
        task_result = await session.execute(task_query.order_by(ProjectTask.created_at))
        tasks = task_result.scalars().all()

        proj_data = {
            "project_name": proj.name,
            "total_tasks": len(tasks),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.pending),
            "done": sum(1 for t in tasks if t.status == TaskStatus.done),
            "tasks": [
                {
                    "content": t.content,
                    "status": t.status.value if t.status else "pending",
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                }
                for t in tasks
            ],
        }
        output.append(proj_data)

    total_pending = sum(p["pending"] for p in output)
    return {
        "success": True,
        "message": f"Tenés {len(output)} proyecto(s) con {total_pending} tarea(s) pendiente(s).",
        "projects": output,
    }


async def handle_complete_project_task(session, user_id: str, args: dict) -> dict:
    """Mark a project task as completed."""
    import uuid
    from sqlalchemy import select
    from datetime import datetime, timezone
    from app.models.project import Project, ProjectTask, TaskStatus

    uid = uuid.UUID(user_id)
    project_name = (args.get("project_name") or "").strip()
    task_content = (args.get("task_content") or "").strip()

    if not project_name or not task_content:
        return {"success": False, "message": "Necesito saber el proyecto y la tarea."}

    # Find project
    result = await session.execute(
        select(Project).where(Project.user_id == uid, Project.name == project_name)
    )
    project = result.scalar_one_or_none()
    if not project:
        return {"success": False, "message": f"No encontré el proyecto '{project_name}'."}

    # Find task (partial match)
    pattern = f"%{task_content}%"
    result = await session.execute(
        select(ProjectTask).where(
            ProjectTask.project_id == project.id,
            ProjectTask.status == TaskStatus.pending,
            ProjectTask.content.ilike(pattern),
        ).limit(1)
    )
    task = result.scalar_one_or_none()
    if not task:
        return {"success": False, "message": f"No encontré una tarea pendiente que coincida con '{task_content}' en '{project_name}'."}

    task.status = TaskStatus.done
    task.completed_at = datetime.now(timezone.utc)
    await session.flush()

    return {
        "success": True,
        "message": f"✅ Tarea '{task.content[:60]}' completada en '{project_name}'.",
    }


async def handle_reopen_project_task(session, user_id: str, args: dict) -> dict:
    """Reopen a completed project task (done → pending)."""
    import uuid
    from sqlalchemy import select
    from app.models.project import Project, ProjectTask, TaskStatus

    uid = uuid.UUID(user_id)
    project_name = (args.get("project_name") or "").strip()
    task_content = (args.get("task_content") or "").strip()

    if not project_name or not task_content:
        return {"success": False, "message": "Necesito saber el proyecto y la tarea a reabrir."}

    result = await session.execute(
        select(Project).where(Project.user_id == uid, Project.name == project_name)
    )
    project = result.scalar_one_or_none()
    if not project:
        return {"success": False, "message": f"No encontré el proyecto '{project_name}'."}

    pattern = f"%{task_content}%"
    result = await session.execute(
        select(ProjectTask).where(
            ProjectTask.project_id == project.id,
            ProjectTask.status == TaskStatus.done,
            ProjectTask.content.ilike(pattern),
        ).limit(1)
    )
    task = result.scalar_one_or_none()
    if not task:
        return {"success": False, "message": f"No encontré una tarea completada que coincida con '{task_content}' en '{project_name}'."}

    task.status = TaskStatus.pending
    task.completed_at = None
    task.reminder_sent = False
    await session.flush()

    return {
        "success": True,
        "message": f"🔄 Tarea '{task.content[:60]}' reabierta en '{project_name}'.",
    }


async def handle_archive_project(session, user_id: str, args: dict) -> dict:
    """Archive a project (set status to archived)."""
    import uuid
    from sqlalchemy import select
    from app.models.project import Project, ProjectStatus

    uid = uuid.UUID(user_id)
    project_name = (args.get("project_name") or "").strip()

    if not project_name:
        return {"success": False, "message": "¿Qué proyecto quieres archivar?"}

    result = await session.execute(
        select(Project).where(
            Project.user_id == uid,
            Project.name == project_name,
            Project.status == ProjectStatus.active,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        return {"success": True, "message": f"El proyecto '{project_name}' no está activo o no existe."}

    project.status = ProjectStatus.archived
    await session.flush()

    return {
        "success": True,
        "message": f"📁 Proyecto '{project_name}' archivado. Tus tareas no se pierden — si quieres reabrirlo, avísame.",
    }


async def handle_save_contact(session, user_id: str, args: dict) -> dict:
    """Save a contact."""
    import uuid
    from sqlalchemy import select
    from app.models.contact import Contact

    name = (args.get("name") or "").strip()
    if not name:
        return {"success": False, "message": "Necesito el nombre del contacto."}

    uid = uuid.UUID(user_id)
    result = await session.execute(
        select(Contact).where(Contact.user_id == uid, Contact.name == name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        if args.get("phone_number"):
            existing.phone_number = args["phone_number"]
        if args.get("email"):
            existing.email = args["email"]
        if args.get("whatsapp_id"):
            existing.whatsapp_id = args["whatsapp_id"]
        if args.get("relationship"):
            existing.relationship = args["relationship"]
        if args.get("notes"):
            existing.contact_notes = args["notes"]
        await session.flush()
        return {"success": True, "message": f"Contacto '{name}' actualizado."}

    contact = Contact(
        user_id=uid, name=name,
        phone_number=args.get("phone_number"),
        email=args.get("email"),
        whatsapp_id=args.get("whatsapp_id"),
        relationship=args.get("relationship"),
        contact_notes=args.get("notes"),
    )
    session.add(contact)
    await session.flush()
    rel_msg = f" ({args['relationship']})" if args.get("relationship") else ""
    return {"success": True, "message": f"Contacto '{name}'{rel_msg} guardado."}


async def handle_list_contacts(session, user_id: str, args: dict) -> dict:
    """List contacts, optionally filtered."""
    import uuid
    from sqlalchemy import select
    from app.models.contact import Contact

    uid = uuid.UUID(user_id)
    search = (args.get("search") or "").strip()
    relationship = (args.get("relationship") or "").strip()

    query = select(Contact).where(Contact.user_id == uid)
    if relationship:
        query = query.where(Contact.relationship == relationship)
    if search:
        query = query.where(Contact.name.ilike(f"%{search}%"))
    query = query.order_by(Contact.name)

    result = await session.execute(query)
    contacts = result.scalars().all()

    if not contacts:
        return {"success": True, "message": "No tienes contactos guardados. Decime 'guardá el contacto X' y empiezo.", "contacts": []}

    contact_list = []
    for c in contacts:
        info_parts = []
        if c.phone_number:
            info_parts.append(f"📱 {c.phone_number}")
        if c.email:
            info_parts.append(f"✉️ {c.email}")
        if c.whatsapp_id:
            info_parts.append(f"💬 WA: {c.whatsapp_id}")
        if c.relationship:
            info_parts.append(f"👥 {c.relationship}")
        contact_list.append({
            "name": c.name,
            "info": " | ".join(info_parts) if info_parts else "sin datos",
            "phone": c.phone_number,
            "email": c.email,
            "relationship": c.relationship,
            "notes": c.contact_notes,
        })

    return {
        "success": True,
        "message": f"Tenés {len(contacts)} contacto(s).",
        "contacts": contact_list,
    }


async def handle_delete_contact(session, user_id: str, args: dict) -> dict:
    """Delete a contact by exact name match."""
    import uuid as uuid_mod
    from sqlalchemy import select
    from app.models.contact import Contact

    uid = uuid_mod.UUID(user_id)
    name = (args.get("name") or "").strip()

    if not name:
        return {"success": False, "message": "¿Qué contacto quieres eliminar?"}

    result = await session.execute(
        select(Contact).where(Contact.user_id == uid, Contact.name == name)
    )
    contact = result.scalar_one_or_none()

    if not contact:
        return {"success": True, "message": f"No tienes un contacto llamado '{name}'."}

    await session.delete(contact)
    await session.flush()

    return {"success": True, "message": f"Contacto '{name}' eliminado."}


# =============================================================================
# TOOL DISPATCHER — maps tool name to handler function
# =============================================================================


async def handle_send_photo(session, user_id: str, args: dict) -> dict:
    """Validate photo exists in MinIO and return info so caller can send it."""
    from app.services import minio as minio_svc

    file_key = (args.get("file_key") or "").strip()
    if not file_key:
        return {"success": False, "message": "No encuentro esa foto. ¿Cuál quieres ver?"}

    # Extract filename from key
    filename = file_key.split("/")[-1] if "/" in file_key else file_key
    caption = (args.get("caption") or "").strip()

    # Validate file exists in MinIO
    try:
        file_bytes = await minio_svc.download_file(file_key)
        if not file_bytes:
            return {"success": False, "message": f"No encontré el archivo '{filename}'. ¿Seguro que está guardado?"}
    except Exception as exc:
        logger.exception("MinIO check failed for send_photo: %s", exc)
        return {"success": False, "message": "No pude acceder al archivo."}

    return {
        "success": True,
        "message": f"Listo, aquí está: {caption or filename}",
        "file_key": file_key,
        "filename": filename,
        "caption": caption,
        "_action": "send_photo",
    }


async def handle_web_search(session, user_id: str, args: dict) -> dict:
    """Search the web for Ecuador-specific current information using DuckDuckGo."""
    from ddgs import DDGS

    query = (args.get("query") or "").strip()
    max_results = min(int(args.get("max_results") or 5), 8)

    if not query:
        return {"success": False, "message": "¿Qué quieres que busque?"}

    logger.info("Web search query: %s (max %d results)", query, max_results)

    try:
        # DuckDuckGo search (runs in thread pool since DDGS is sync)
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))

        if not raw_results:
            return {
                "success": True,
                "message": f"No encontré resultados para '{query}'.",
                "results": [],
            }

        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("body", "")[:300],
                "url": r.get("href", ""),
            })

        return {
            "success": True,
            "message": f"Encontré {len(results)} resultado(s) web sobre '{query}'.",
            "results": results,
            "query": query,
        }

    except Exception as exc:
        logger.exception("Web search failed: %s", exc)
        return {
            "success": False,
            "message": "No pude buscar en internet ahora. ¿Intentamos más tarde?",
        }


async def handle_list_my_vehicles(session, user_id: str, args: dict) -> dict:
    """List all vehicles for the current user with key data."""
    import uuid as uuid_mod
    from app.models.vehicle import Vehicle

    result = await session.execute(
        select(Vehicle).where(
            Vehicle.user_id == uuid_mod.UUID(user_id),
            Vehicle.deleted_at.is_(None),
        )
    )
    vehicles = result.scalars().all()

    if not vehicles:
        return {
            "success": True,
            "message": "No tienes vehículos registrados todavía. Mándame la placa y te lo guardo.",
            "vehicles": [],
        }

    vehicle_list = []
    for v in vehicles:
        vehicle_list.append({
            "id": str(v.id),
            "plate": v.plate,
            "brand": v.brand,
            "model": v.model,
            "year": v.year,
            "color": v.color,
            "pico_y_placa_days": v.pico_y_placa_days,
            "next_matriculation": str(v.next_matriculation) if v.next_matriculation else None,
            "soat_expiry": str(v.soat_expiry) if v.soat_expiry else None,
            "rtv_expiry": str(v.rtv_expiry) if v.rtv_expiry else None,
            "notes": v.notes,
        })

    return {
        "success": True,
        "message": f"Tenés {len(vehicles)} vehículo(s) registrado(s).",
        "vehicles": vehicle_list,
    }


async def handle_add_maintenance(session, user_id: str, args: dict) -> dict:
    """Add a maintenance record for a vehicle."""
    from datetime import date
    import uuid as uuid_mod
    from app.models.vehicle import Vehicle, VehicleMaintenance, MaintenanceType

    vehicle_ref = (args.get("vehicle_id_or_plate") or "").upper().strip().replace("-", "")
    if not vehicle_ref:
        return {"success": False, "message": "¿A cuál vehículo le hiciste el mantenimiento? Decime la placa."}

    user_uuid = uuid_mod.UUID(user_id)

    # Find vehicle by id or plate
    try:
        vid = uuid_mod.UUID(vehicle_ref)
        result = await session.execute(
            select(Vehicle).where(Vehicle.id == vid, Vehicle.user_id == user_uuid)
        )
    except ValueError:
        result = await session.execute(
            select(Vehicle).where(
                Vehicle.plate == vehicle_ref,
                Vehicle.user_id == user_uuid,
                Vehicle.deleted_at.is_(None),
            )
        )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        return {
            "success": False,
            "message": f"No encontré el vehículo '{vehicle_ref}'. ¿Está bien escrita la placa?"
        }

    # Parse maintenance type
    mtype_str = (args.get("maintenance_type") or "other").lower().strip()
    try:
        mtype = MaintenanceType(mtype_str)
    except ValueError:
        mtype = MaintenanceType.other

    # Parse date
    performed_at_str = args.get("performed_at")
    performed_at = None
    if performed_at_str:
        try:
            performed_at = date.fromisoformat(performed_at_str)
        except (ValueError, TypeError):
            pass
    if not performed_at:
        performed_at = date.today()

    # Parse other date fields
    next_at = None
    if args.get("next_at"):
        try:
            next_at = date.fromisoformat(args["next_at"])
        except (ValueError, TypeError):
            pass

    maint = VehicleMaintenance(
        vehicle_id=vehicle.id,
        maintenance_type=mtype,
        description=args.get("description"),
        cost=args.get("cost"),
        mileage_km=args.get("mileage_km"),
        performed_at=performed_at,
        performed_by=args.get("performed_by"),
        next_at=next_at,
        next_mileage_km=args.get("next_mileage_km"),
        receipt_file_key=args.get("file_key"),
        notes=args.get("notes"),
    )
    session.add(maint)
    await session.flush()

    # Build friendly type name
    type_labels = {
        "oil_change": "cambio de aceite",
        "brakes": "frenos",
        "tires": "llantas",
        "battery": "batería",
        "general": "mantenimiento general",
        "other": "otro mantenimiento",
    }
    type_label = type_labels.get(mtype.value, mtype.value)

    cost_msg = f", ${args['cost']:.0f}" if args.get("cost") else ""
    km_msg = f", {args['mileage_km']} km" if args.get("mileage_km") else ""
    workshop_msg = f" en {args['performed_by']}" if args.get("performed_by") else ""

    return {
        "success": True,
        "message": (
            f"Registrado: {type_label} para {vehicle.plate}"
            f"{cost_msg}{km_msg}{workshop_msg}."
        ),
        "maintenance_id": str(maint.id),
    }


async def handle_list_maintenances(session, user_id: str, args: dict) -> dict:
    """List maintenance history for a vehicle."""
    import uuid as uuid_mod
    from app.models.vehicle import Vehicle, VehicleMaintenance

    vehicle_ref = (args.get("vehicle_id_or_plate") or "").upper().strip().replace("-", "")
    if not vehicle_ref:
        return {"success": False, "message": "¿De cuál vehículo quieres ver los mantenimientos? Decime la placa."}

    user_uuid = uuid_mod.UUID(user_id)

    # Find vehicle
    try:
        vid = uuid_mod.UUID(vehicle_ref)
        result = await session.execute(
            select(Vehicle).where(Vehicle.id == vid, Vehicle.user_id == user_uuid)
        )
    except ValueError:
        result = await session.execute(
            select(Vehicle).where(
                Vehicle.plate == vehicle_ref,
                Vehicle.user_id == user_uuid,
                Vehicle.deleted_at.is_(None),
            )
        )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        return {
            "success": False,
            "message": f"No encontré el vehículo '{vehicle_ref}'."
        }

    maints_result = await session.execute(
        select(VehicleMaintenance)
        .where(VehicleMaintenance.vehicle_id == vehicle.id)
        .order_by(VehicleMaintenance.performed_at.desc())
        .limit(20)
    )
    maintenances = maints_result.scalars().all()

    if not maintenances:
        return {
            "success": True,
            "message": f"{vehicle.plate} no tiene mantenimientos registrados todavía.",
            "maintenances": [],
        }

    type_labels = {
        "oil_change": "🛢️ Cambio de aceite",
        "brakes": "🛑 Frenos",
        "tires": "🛞 Llantas",
        "battery": "🔋 Batería",
        "general": "🔧 General",
        "other": "📋 Otro",
    }

    maint_list = []
    for m in maintenances:
        maint_list.append({
            "id": str(m.id),
            "type": m.maintenance_type.value if m.maintenance_type else "other",
            "type_label": type_labels.get(m.maintenance_type.value if m.maintenance_type else "other", "Otro"),
            "description": m.description,
            "cost": m.cost,
            "mileage_km": m.mileage_km,
            "performed_at": str(m.performed_at) if m.performed_at else None,
            "performed_by": m.performed_by,
            "next_at": str(m.next_at) if m.next_at else None,
            "next_mileage_km": m.next_mileage_km,
            "receipt_file_key": m.receipt_file_key,
        })

    return {
        "success": True,
        "message": f"{vehicle.plate} tiene {len(maintenances)} mantenimiento(s) registrado(s).",
        "vehicle_plate": vehicle.plate,
        "maintenances": maint_list,
    }


async def handle_delete_vehicle(session, user_id: str, args: dict) -> dict:
    """Soft-delete a vehicle by plate."""
    import uuid as uuid_mod
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.models.vehicle import Vehicle

    uid = uuid_mod.UUID(user_id)
    plate = (args.get("plate") or "").upper().strip().replace("-", "")

    if not plate:
        return {"success": False, "message": "¿Qué vehículo quieres eliminar? Decime la placa."}

    result = await session.execute(
        select(Vehicle).where(
            Vehicle.user_id == uid,
            Vehicle.plate == plate,
            Vehicle.deleted_at.is_(None),
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        return {"success": True, "message": f"No tienes un vehículo con placa {plate}."}

    vehicle.deleted_at = datetime.now(timezone.utc)
    await session.flush()

    return {"success": True, "message": f"Vehículo {plate} eliminado."}


async def handle_update_vehicle(session, user_id: str, args: dict) -> dict:
    """Update vehicle fields by plate."""
    import uuid as uuid_mod
    from sqlalchemy import select
    from app.models.vehicle import Vehicle
    from app.services.vehicle_rules import evaluate_vehicle_rules
    from datetime import date

    uid = uuid_mod.UUID(user_id)
    plate = (args.get("plate") or "").upper().strip().replace("-", "")

    if not plate:
        return {"success": False, "message": "Necesito la placa del vehículo a actualizar."}

    result = await session.execute(
        select(Vehicle).where(
            Vehicle.user_id == uid,
            Vehicle.plate == plate,
            Vehicle.deleted_at.is_(None),
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        return {"success": True, "message": f"No tienes un vehículo con placa {plate}."}

    changed = []

    # Update plate → recalculate rules
    new_plate = args.get("new_plate")
    if new_plate:
        new_plate_clean = new_plate.upper().strip().replace("-", "")
        if new_plate_clean != vehicle.plate:
            vehicle.plate = new_plate_clean
            changed.append(f"placa → {new_plate_clean}")
            # Recalculate vehicle rules
            try:
                rules = evaluate_vehicle_rules(new_plate_clean, None, date.today())
                vehicle.last_digit = rules["last_digit"]
                vehicle.pico_y_placa_days = rules["pico_y_placa_days"]
                vehicle.next_matriculation = date.fromisoformat(rules["next_matriculation"])
            except Exception:
                pass

    if args.get("brand"):
        vehicle.brand = args["brand"]
        changed.append(f"marca → {args['brand']}")
    if args.get("model"):
        vehicle.model = args["model"]
        changed.append(f"modelo → {args['model']}")
    if args.get("year"):
        vehicle.year = args["year"]
        changed.append(f"año → {args['year']}")
    if args.get("color"):
        vehicle.color = args["color"]
        changed.append(f"color → {args['color']}")
    if args.get("notes"):
        vehicle.notes = args["notes"]
        changed.append("notas")

    if not changed:
        return {"success": True, "message": f"No hay cambios para {plate}."}

    await session.flush()

    return {
        "success": True,
        "message": f"Vehículo {plate} actualizado: {', '.join(changed)}.",
    }


# =============================================================================
# SUBSCRIPTION HANDLERS
# =============================================================================

async def handle_subscribe_to_plan(session, user_id: str, args: dict) -> dict:
    """Create a pending payment and return payment instructions with PayPhone link + transfer info."""
    import uuid as uuid_mod
    from sqlalchemy import select
    from app.models.subscription import Subscription, Payment, PaymentStatus, PaymentMethod, RenewalType
    from app.models.subscription_plan import SubscriptionPlan
    from app.models.business import BusinessInfo
    from app.services import payphone as payphone_svc
    from app.services import deuna as deuna_svc

    uid = uuid_mod.UUID(user_id)
    plan_slug = (args.get("plan_slug") or "basic").strip()
    renewal = (args.get("renewal") or "monthly").strip()

    # Find plan
    plan_result = await session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.slug == plan_slug)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        return {"success": False, "message": f"El plan '{plan_slug}' no existe. Planes disponibles: básico ($4.99), premium ($9.99), familia ($14.99)."}

    # Find or create subscription
    sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == uid)
    )
    subscription = sub_result.scalar_one_or_none()

    if not subscription:
        subscription = Subscription(
            user_id=uid,
            plan_id=plan.id,
            status="pending",
        )
        session.add(subscription)
        await session.flush()
    else:
        subscription.plan_id = plan.id

    # Calculate price
    if renewal == "annual":
        price = float(plan.price_annual_usd)
    else:
        price = float(plan.price_monthly_usd)

    if price <= 0:
        subscription.status = "active"
        await session.flush()
        return {
            "success": True,
            "message": f"✅ Plan {plan.name} activado. ¡Bienvenido a Lucho!",
            "plan": plan.name,
        }

    # Set renewal type
    try:
        subscription.renewal_type = RenewalType(renewal)
    except ValueError:
        subscription.renewal_type = RenewalType.monthly

    # Create pending payment
    pay_ref = f"SUB-{str(uid)[:8]}-{plan_slug}-{uuid_mod.uuid4().hex[:6]}"
    payment = Payment(
        user_id=uid,
        subscription_id=subscription.id,
        amount=price,
        currency="USD",
        payment_method=PaymentMethod.other,
        gateway="payphone",
        gateway_payment_id=pay_ref,
        status=PaymentStatus.pending,
    )
    session.add(payment)
    await session.flush()

    # Load business info for transfer instructions
    biz_result = await session.execute(
        select(BusinessInfo).where(BusinessInfo.is_active == True)
    )
    biz = biz_result.scalar_one_or_none()

    # Build payment message
    plan_label = plan.name
    renewal_label = "año" if renewal == "annual" else "mes"

    lines = [
        f"📱 *Suscribite al plan {plan_label}*",
        "",
        f"💰 *${price:.2f}* / {renewal_label}",
        f"📦 {plan.description}",
        "",
    ]

    # Option 1: PayPhone (app + web formulario de tarjeta)
    pp_payment = await payphone_svc.create_payment(
        amount=price,
        description=f"Lucho — Plan {plan.name} ({renewal})",
        reference=pay_ref,
    )

    # Option 2: DeUna (Botón de pago interbancario — Pichincha y otros bancos)
    deuna_payment = await deuna_svc.create_payment(
        amount=price,
        description=f"Lucho — Plan {plan.name}",
        reference=pay_ref,
    )

    if pp_payment and pp_payment.payment_url:
        lines.append("1️⃣ *Pago con tarjeta (PayPhone)*")
        lines.append(f"   👉 {pp_payment.payment_url}")
        lines.append("   Abrí el link en tu celular o compu.")
        lines.append("   Se abre la app o pagás con tarjeta en la web.")
        lines.append("")

    if deuna_payment and deuna_payment.payment_url:
        qr_info = f"\n   📱 Código QR: {deuna_payment.payment_url}" if deuna_payment.payment_url else ""
        lines.append("2️⃣ *DeUna — Pago con QR*")
        lines.append(f"   👉 {deuna_payment.payment_url}")
        lines.append("   Escaneá el código QR desde tu app bancaria.")
        lines.append("   Funciona con Pichincha, Guayaquil, Produbanco, etc.")
        lines.append("")

    # Option 3: Bank transfer
    transfer_number = 3 if (pp_payment or deuna_payment) else 1
    if biz:
        lines.append(f"{transfer_number}️⃣ *Transferencia bancaria*")
        lines.append(f"   🏦 {biz.company_name}")
        lines.append(f"   📋 RUC: {biz.ruc}")
        lines.append(f"   💳 {biz.bank_name} — Cta. {biz.account_type} #{biz.account_number}")
        lines.append("")
        lines.append("   Envianos el comprobante y activamos tu plan.")

    return {
        "success": True,
        "message": "\n".join(lines),
        "payment_url": pp_payment.payment_url if pp_payment else None,
        "plan": plan.name,
        "price": price,
        "renewal": renewal_label,
        "reference": pay_ref,
    }


async def handle_update_billing_info(session, user_id: str, args: dict) -> dict:
    """Create or update a billing profile for SRI invoicing."""
    import uuid as uuid_mod
    from sqlalchemy import select, update
    from app.models.billing_info import BillingInfo

    uid = uuid_mod.UUID(user_id)
    label = (args.get("label") or "personal").strip()
    full_name = (args.get("full_name") or "").strip()
    id_number = (args.get("id_number") or "").strip()
    id_type = (args.get("id_type") or "cedula").strip()
    email = (args.get("email") or "").strip()
    phone = args.get("phone")
    address = (args.get("address") or "").strip()

    if not full_name or not id_number or not email or not address:
        return {"success": False, "message": "Necesito: nombre, cédula/RUC, correo y dirección para la factura."}

    # Upsert: create or update billing profile with this label
    result = await session.execute(
        select(BillingInfo).where(
            BillingInfo.user_id == uid,
            BillingInfo.label == label,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.full_name = full_name
        existing.id_number = id_number
        existing.id_type = id_type
        existing.email = email
        existing.phone = phone
        existing.address = address
        await session.flush()
        action = "actualizado"
    else:
        # If this is the first profile, mark as default
        count_result = await session.execute(
            select(BillingInfo).where(BillingInfo.user_id == uid)
        )
        is_first = len(count_result.scalars().all()) == 0

        profile = BillingInfo(
            user_id=uid,
            label=label,
            full_name=full_name,
            id_number=id_number,
            id_type=id_type,
            email=email,
            phone=phone,
            address=address,
            is_default=is_first,
        )
        session.add(profile)
        await session.flush()
        action = "guardado"

    id_label = "RUC" if id_type == "ruc" else "Cédula" if id_type == "cedula" else id_type.upper()
    return {
        "success": True,
        "message": (
            f"✅ Datos de facturación {action}s.\n\n"
            f"📋 {full_name}\n"
            f"🆔 {id_label}: {id_number}\n"
            f"📧 {email}\n"
            f"📍 {address}\n\n"
            f"Cuando pagues tu suscripción, la factura se emitirá con estos datos."
        ),
        "label": label,
        "id_type": id_type,
    }


# =============================================================================
# BILLING HANDLERS — cotizaciones, clientes, productos
# =============================================================================


async def _get_iva_rate(session) -> float:
    """Get IVA rate from BusinessInfo, falling back to config."""
    from sqlalchemy import select
    from app.models.business import BusinessInfo
    from app.config import settings

    result = await session.execute(
        select(BusinessInfo).where(BusinessInfo.is_active == True)
    )
    biz = result.scalar_one_or_none()
    if biz and biz.iva_rate:
        return float(biz.iva_rate)
    return float(getattr(settings, 'IVA_RATE', 15.0))


async def handle_create_quote(session, user_id: str, args: dict) -> dict:
    """Create a quote with auto-calculated IVA and total."""
    import uuid as uuid_mod
    from datetime import date
    from sqlalchemy import select, func
    from app.models.billing import (
        BillingDocument, BillingDocumentItem,
        BillingDocumentType, BillingDocumentStatus,
    )

    uid = uuid_mod.UUID(user_id)
    client_name = (args.get("client_name") or "").strip()
    client_id_number = args.get("client_id_number")
    items = args.get("items") or []
    notes = args.get("notes")

    if not client_name:
        return {"success": False, "message": "¿A nombre de quién va la cotización?"}
    if not items:
        return {"success": False, "message": "Necesito al menos un ítem para la cotización."}

    iva_rate = await _get_iva_rate(session)
    iva_factor = iva_rate / 100.0

    # Generate sequential quote number
    count_result = await session.execute(
        select(func.count(BillingDocument.id)).where(
            BillingDocument.user_id == uid,
            BillingDocument.document_type == BillingDocumentType.quote,
        )
    )
    next_num = (count_result.scalar_one() or 0) + 1
    quote_number = f"COT-{next_num:04d}"

    # Calculate totals
    line_items = []
    subtotal = 0.0
    iva_total = 0.0

    for it in items:
        desc = (it.get("description") or "Ítem").strip()
        qty = float(it.get("quantity") or 1)
        price = float(it.get("unit_price") or 0)
        line = qty * price
        subtotal += line
        iva_total += line * iva_factor
        line_items.append({
            "description": desc,
            "quantity": qty,
            "unit_price": price,
            "line_total": round(line, 2),
        })

    total = round(subtotal + iva_total, 2)

    # Create document
    doc = BillingDocument(
        user_id=uid,
        client_name=client_name,
        client_id_number=client_id_number,
        document_type=BillingDocumentType.quote,
        quote_number=quote_number,
        issue_date=date.today(),
        subtotal=round(subtotal, 2),
        iva_rate=iva_rate,
        iva_amount=round(iva_total, 2),
        total=total,
        status=BillingDocumentStatus.draft,
        notes=notes,
    )
    session.add(doc)
    await session.flush()

    # Create line items
    for li in line_items:
        item = BillingDocumentItem(
            document_id=doc.id,
            description=li["description"],
            quantity=li["quantity"],
            unit_price=li["unit_price"],
            has_iva=True,
            line_total=li["line_total"],
        )
        session.add(item)

    await session.flush()

    # Build response
    lines = [
        f"📋 *Cotización {quote_number}*",
        f"Cliente: {client_name}",
        "",
    ]
    for li in line_items:
        if li["quantity"] == 1:
            lines.append(f"• {li['description']} — ${li['line_total']:.2f}")
        else:
            lines.append(f"• {li['quantity']:.0f}x {li['description']} — ${li['line_total']:.2f}")

    lines.append("")
    lines.append(f"📦 Subtotal: ${subtotal:.2f}")
    lines.append(f"🧾 IVA {iva_rate:.0f}%: ${iva_total:.2f}")
    lines.append(f"💰 *Total: ${total:.2f}*")
    if notes:
        lines.append(f"\n📝 {notes}")

    return {
        "success": True,
        "message": "\n".join(lines),
        "quote_number": quote_number,
        "total": total,
        "iva_rate": iva_rate,
    }


async def handle_list_my_quotes(session, user_id: str, args: dict) -> dict:
    """List quotes with status and period filters."""
    import uuid as uuid_mod
    from datetime import date, datetime
    from sqlalchemy import select
    from app.models.billing import BillingDocument, BillingDocumentType, BillingDocumentStatus

    uid = uuid_mod.UUID(user_id)
    status_filter = args.get("status", "all")
    period = args.get("period", "this_month")

    # Date range
    today = date.today()
    if period == "this_month":
        start = today.replace(day=1)
        end = today
    elif period == "last_month":
        if today.month == 1:
            start = date(today.year - 1, 12, 1)
            end = date(today.year, 1, 1)
        else:
            start = date(today.year, today.month - 1, 1)
            end = today.replace(day=1)
    else:
        start = date(2020, 1, 1)
        end = today

    query = select(BillingDocument).where(
        BillingDocument.user_id == uid,
        BillingDocument.document_type == BillingDocumentType.quote,
        BillingDocument.issue_date >= start,
        BillingDocument.issue_date <= end,
    )

    if status_filter != "all":
        try:
            st = BillingDocumentStatus(status_filter)
            query = query.where(BillingDocument.status == st)
        except ValueError:
            pass

    result = await session.execute(query.order_by(BillingDocument.issue_date.desc()).limit(20))
    quotes = result.scalars().all()

    if not quotes:
        return {"success": True, "message": "No tienes cotizaciones en este período. Decime 'cotización para...' y creamos una.", "quotes": [], "total": 0}

    total_amount = sum(q.total for q in quotes)
    quote_list = [
        {
            "quote_number": q.quote_number,
            "client_name": q.client_name,
            "total": q.total,
            "status": q.status.value if q.status else "draft",
            "issue_date": str(q.issue_date),
            "iva_rate": q.iva_rate,
        }
        for q in quotes
    ]

    return {
        "success": True,
        "message": f"Tenés {len(quotes)} cotización(es) — Total: ${total_amount:.2f}.",
        "quotes": quote_list,
        "total": len(quotes),
        "total_amount": total_amount,
    }


async def handle_save_billing_client(session, user_id: str, args: dict) -> dict:
    """Save or update a billing client."""
    import uuid as uuid_mod
    from sqlalchemy import select
    from app.models.billing import BillingClient, BillingIdType

    uid = uuid_mod.UUID(user_id)
    name = (args.get("name") or "").strip()
    id_number = (args.get("id_number") or "").strip()

    if not name or not id_number:
        return {"success": False, "message": "Necesito nombre y cédula/RUC del cliente."}

    id_type_str = args.get("id_type", "cedula")
    try:
        id_type = BillingIdType(id_type_str)
    except ValueError:
        id_type = BillingIdType.cedula

    # Upsert
    result = await session.execute(
        select(BillingClient).where(
            BillingClient.user_id == uid,
            BillingClient.id_number == id_number,
        )
    )
    client = result.scalar_one_or_none()

    if client:
        client.name = name
        client.id_type = id_type
        client.email = args.get("email")
        client.phone = args.get("phone")
        client.address = args.get("address")
        action = "actualizado"
    else:
        client = BillingClient(
            user_id=uid, name=name, id_type=id_type, id_number=id_number,
            email=args.get("email"), phone=args.get("phone"), address=args.get("address"),
        )
        session.add(client)
        action = "guardado"

    await session.flush()

    return {
        "success": True,
        "message": f"Cliente '{name}' {action}. Ahora puedes decir 'cotización para {name}'.",
        "client_name": name,
        "id_number": id_number,
    }


async def handle_save_billing_product(session, user_id: str, args: dict) -> dict:
    """Save or update a billing product."""
    import uuid as uuid_mod
    from sqlalchemy import select
    from app.models.billing import BillingProduct

    uid = uuid_mod.UUID(user_id)
    name = (args.get("name") or "").strip()
    unit_price = float(args.get("unit_price") or 0)

    if not name or unit_price <= 0:
        return {"success": False, "message": "Necesito nombre y precio del producto."}

    has_iva = args.get("has_iva", True)

    result = await session.execute(
        select(BillingProduct).where(
            BillingProduct.user_id == uid,
            BillingProduct.name == name,
        )
    )
    product = result.scalar_one_or_none()

    if product:
        product.unit_price = unit_price
        product.has_iva = has_iva
        product.code = args.get("code")
        action = "actualizado"
    else:
        product = BillingProduct(
            user_id=uid, name=name, unit_price=unit_price,
            has_iva=has_iva, code=args.get("code"),
        )
        session.add(product)
        action = "agregado"

    await session.flush()

    iva_msg = "+IVA" if has_iva else "sin IVA"
    return {
        "success": True,
        "message": f"Producto '{name}' {action} al catálogo — ${unit_price:.2f} ({iva_msg}).",
        "product_name": name,
        "unit_price": unit_price,
    }


# =============================================================================
# FINANCE HANDLERS
# =============================================================================

async def handle_add_transaction(session, user_id: str, args: dict) -> dict:
    """Register an expense or income."""
    import uuid as _uuid_mod
    from app.services.persistence import persist_transaction

    txn_type = args.get("type", "expense")
    amount = args.get("amount", 0)
    category = args.get("category", "other_expense")
    description = args.get("description", "")
    transaction_date = args.get("transaction_date")
    payment_method = args.get("payment_method")

    if not amount or float(amount) <= 0:
        return {"success": False, "message": "Necesito el monto para registrar el gasto."}

    try:
        txn = await persist_transaction(
            session=session,
            user_id=_uuid_mod.UUID(user_id),
            type=txn_type,
            amount=float(amount),
            category=category,
            description=description,
            transaction_date=transaction_date,
            payment_method=payment_method,
        )
        emoji = "💸" if txn.type.value == "expense" else "💰"
        cat_label = txn.category.value.replace("_", " ").title()
        return {
            "success": True,
            "message": f"{emoji} Registrado: {description or cat_label} — ${amount:.2f} ({cat_label}).",
            "transaction_id": str(txn.id),
            "amount": amount,
            "category": txn.category.value,
            "type": txn.type.value,
        }
    except Exception as exc:
        logger.exception("Failed to add transaction: %s", exc)
        return {"success": False, "message": "No pude registrar el gasto. ¿Intentamos de nuevo?"}


async def handle_list_transactions(session, user_id: str, args: dict) -> dict:
    """Query transactions by period and category."""
    import uuid as _uuid_mod
    from datetime import date, datetime, timedelta
    from sqlalchemy import select, func
    from app.models.transaction import Transaction

    txn_type = args.get("type", "all")
    category = args.get("category")
    period = args.get("period", "this_month")
    group_by = args.get("group_by", "none")

    today = date.today()

    # Calculate date range
    if period == "today":
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        period_label = "hoy"
    elif period == "yesterday":
        yesterday = today - timedelta(days=1)
        start = datetime.combine(yesterday, datetime.min.time())
        end = datetime.combine(yesterday, datetime.max.time())
        period_label = "ayer"
    elif period == "this_week":
        start = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
        end = datetime.combine(start.date() + timedelta(days=6), datetime.max.time())
        period_label = "esta semana"
    elif period == "last_week":
        this_monday = today - timedelta(days=today.weekday())
        start = datetime.combine(this_monday - timedelta(days=7), datetime.min.time())
        end = datetime.combine(this_monday - timedelta(days=1), datetime.max.time())
        period_label = "la semana pasada"
    elif period == "last_month":
        first_of_this_month = today.replace(day=1)
        start = datetime.combine((first_of_this_month - timedelta(days=1)).replace(day=1), datetime.min.time())
        end = datetime.combine(first_of_this_month - timedelta(days=1), datetime.max.time())
        period_label = "el mes pasado"
    else:  # this_month
        start = datetime.combine(today.replace(day=1), datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        period_label = "este mes"

    # Build query
    filters = [
        Transaction.user_id == _uuid_mod.UUID(user_id),
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= end,
    ]
    if txn_type != "all":
        filters.append(Transaction.type == txn_type)
    if category:
        filters.append(Transaction.category == category)

    try:
        if group_by == "category":
            result = await session.execute(
                select(
                    Transaction.category,
                    Transaction.type,
                    func.sum(Transaction.amount).label("total"),
                    func.count(Transaction.id).label("count"),
                )
                .where(*filters)
                .group_by(Transaction.category, Transaction.type)
                .order_by(func.sum(Transaction.amount).desc())
            )
            rows = result.all()
            items = [
                {
                    "category": r.category.value if hasattr(r.category, 'value') else r.category,
                    "type": r.type.value if hasattr(r.type, 'value') else r.type,
                    "total": float(r.total),
                    "count": r.count,
                }
                for r in rows
            ]
            total = sum(i["total"] for i in items)
            return {
                "success": True,
                "period": period_label,
                "total": total,
                "by_category": items,
            }
        else:
            result = await session.execute(
                select(Transaction)
                .where(*filters)
                .order_by(Transaction.transaction_date.desc())
                .limit(50)
            )
            txns = result.scalars().all()
            items = [
                {
                    "id": str(t.id),
                    "type": t.type.value,
                    "amount": float(t.amount),
                    "category": t.category.value,
                    "description": t.description,
                    "date": t.transaction_date.strftime("%Y-%m-%d"),
                    "payment_method": t.payment_method,
                }
                for t in txns
            ]
            total = sum(i["amount"] for i in items)
            return {
                "success": True,
                "period": period_label,
                "count": len(items),
                "total": total,
                "transactions": items[:20],
            }
    except Exception as exc:
        logger.exception("Failed to list transactions: %s", exc)
        return {"success": False, "message": "No pude consultar tus gastos. ¿Intentamos de nuevo?"}


async def handle_get_balance(session, user_id: str, args: dict) -> dict:
    """Get financial balance: income, expenses, net."""
    import uuid as _uuid_mod
    from datetime import date, datetime
    from sqlalchemy import select, func
    from app.models.transaction import Transaction, TransactionType

    period = args.get("period", "this_month")
    today = date.today()

    if period == "last_month":
        first_of_this_month = today.replace(day=1)
        start = datetime.combine((first_of_this_month - timedelta(days=1)).replace(day=1), datetime.min.time())
        end = datetime.combine(first_of_this_month - timedelta(days=1), datetime.max.time())
        period_label = "el mes pasado"
    elif period == "this_year":
        from datetime import timedelta
        start = datetime.combine(today.replace(month=1, day=1), datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        period_label = "este año"
    else:
        start = datetime.combine(today.replace(day=1), datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        period_label = "este mes"

    try:
        # Income total
        income_result = await session.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.user_id == _uuid_mod.UUID(user_id),
                Transaction.type == TransactionType.income,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
        )
        income = float(income_result.scalar_one())

        # Expense total
        expense_result = await session.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.user_id == _uuid_mod.UUID(user_id),
                Transaction.type == TransactionType.expense,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
        )
        expenses = float(expense_result.scalar_one())

        balance = income - expenses

        # Top expense categories
        top_result = await session.execute(
            select(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                Transaction.user_id == _uuid_mod.UUID(user_id),
                Transaction.type == TransactionType.expense,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(5)
        )
        top_categories = [
            {"category": r.category.value, "total": float(r.total)}
            for r in top_result.all()
        ]

        return {
            "success": True,
            "period": period_label,
            "income": income,
            "expenses": expenses,
            "balance": balance,
            "top_expense_categories": top_categories,
        }
    except Exception as exc:
        logger.exception("Failed to get balance: %s", exc)
        return {"success": False, "message": "No pude calcular tu balance. ¿Intentamos de nuevo?"}


async def handle_set_budget(session, user_id: str, args: dict) -> dict:
    """Create or update a budget for a category."""
    import uuid as _uuid_mod
    from app.services.persistence import persist_budget

    category = args.get("category", "")
    amount = args.get("amount", 0)
    period = args.get("period", "monthly")
    alert_threshold = args.get("alert_threshold", 80)

    if not category or float(amount) <= 0:
        return {"success": False, "message": "Necesito la categoría y el monto del presupuesto."}

    try:
        budget = await persist_budget(
            session=session,
            user_id=_uuid_mod.UUID(user_id),
            category=category,
            amount=float(amount),
            period=period,
            alert_threshold=int(alert_threshold),
        )
        cat_label = budget.category.value.replace("_", " ").title()
        period_label = "mensual" if budget.period.value == "monthly" else "semanal"
        return {
            "success": True,
            "message": f"Presupuesto {period_label}: {cat_label} ${float(amount):.2f}. Te aviso al {alert_threshold}%.",
            "budget_id": str(budget.id),
            "category": budget.category.value,
            "amount": float(budget.amount),
        }
    except Exception as exc:
        logger.exception("Failed to set budget: %s", exc)
        return {"success": False, "message": "No pude configurar el presupuesto. ¿Intentamos de nuevo?"}


async def handle_check_budget(session, user_id: str, args: dict) -> dict:
    """Check budget status and spending progress."""
    import uuid as _uuid_mod
    from datetime import date, datetime
    from sqlalchemy import select, func
    from app.models.transaction import Budget, Transaction, TransactionType, TransactionCategory

    category = args.get("category")
    today = date.today()
    start = datetime.combine(today.replace(day=1), datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    try:
        # Get active budgets
        budget_filters = [
            Budget.user_id == _uuid_mod.UUID(user_id),
            Budget.is_active == True,
        ]
        if category:
            try:
                cat_enum = TransactionCategory(category)
                budget_filters.append(Budget.category == cat_enum)
            except ValueError:
                return {"success": False, "message": f"No conozco la categoría '{category}'."}

        budget_result = await session.execute(
            select(Budget).where(*budget_filters)
        )
        budgets = budget_result.scalars().all()

        if not budgets:
            msg = f"No tienes presupuesto para '{category}'." if category else "No tienes presupuestos configurados."
            return {"success": True, "message": msg, "budgets": []}

        items = []
        for budget in budgets:
            # Get spending for this category this month
            spent_result = await session.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0))
                .where(
                    Transaction.user_id == _uuid_mod.UUID(user_id),
                    Transaction.type == TransactionType.expense,
                    Transaction.category == budget.category,
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end,
                )
            )
            spent = float(spent_result.scalar_one())
            percentage = round((spent / float(budget.amount)) * 100) if float(budget.amount) > 0 else 0
            over_budget = percentage >= 100
            near_limit = not over_budget and percentage >= budget.alert_threshold

            items.append({
                "category": budget.category.value,
                "budget": float(budget.amount),
                "spent": spent,
                "remaining": max(float(budget.amount) - spent, 0),
                "percentage": percentage,
                "over_budget": over_budget,
                "near_limit": near_limit,
            })

        return {"success": True, "budgets": items}
    except Exception as exc:
        logger.exception("Failed to check budget: %s", exc)
        return {"success": False, "message": "No pude revisar tus presupuestos. ¿Intentamos de nuevo?"}
TOOL_HANDLERS: dict[str, Any] = {
    "save_vehicle": handle_save_vehicle,
    "list_my_vehicles": handle_list_my_vehicles,
    "add_maintenance": handle_add_maintenance,
    "list_maintenances": handle_list_maintenances,
    "delete_vehicle": handle_delete_vehicle,
    "update_vehicle": handle_update_vehicle,
    "subscribe_to_plan": handle_subscribe_to_plan,
    "update_billing_info": handle_update_billing_info,
    "create_quote": handle_create_quote,
    "list_my_quotes": handle_list_my_quotes,
    "save_billing_client": handle_save_billing_client,
    "save_billing_product": handle_save_billing_product,
    "save_document": handle_save_document,
    "list_my_documents": handle_list_my_documents,
    "save_event": handle_save_event,
    "list_my_events": handle_list_my_events,
    "save_list": handle_save_list,
    "list_items": handle_list_items,
    "complete_item": handle_complete_item,
    "delete_list": handle_delete_list,
    "save_note": handle_save_note,
    "list_my_notes": handle_list_my_notes,
    "delete_note": handle_delete_note,
    "search_my_data": handle_search_data,
    "get_my_summary": handle_get_summary,
    "update_last": handle_update_last,
    "check_vehicle_info": handle_check_vehicle_info,
    "search_conversation": handle_search_conversation,
    "analyze_image": handle_analyze_image,
    "save_project_task": handle_save_project_task,
    "list_project_tasks": handle_list_project_tasks,
    "complete_project_task": handle_complete_project_task,
    "reopen_project_task": handle_reopen_project_task,
    "archive_project": handle_archive_project,
    "save_contact": handle_save_contact,
    "list_contacts": handle_list_contacts,
    "delete_contact": handle_delete_contact,
    "send_photo": handle_send_photo,
    "web_search": handle_web_search,
    "add_transaction": handle_add_transaction,
    "list_transactions": handle_list_transactions,
    "get_balance": handle_get_balance,
    "set_budget": handle_set_budget,
    "check_budget": handle_check_budget,
}


async def execute_tool(session, user_id: str, tool_name: str, tool_args: dict) -> dict:
    """
    Execute a tool by name. Called by the agent loop when the LLM requests a tool call.

    Args:
        session: SQLAlchemy async session
        user_id: UUID string of the current user
        tool_name: Name of the tool to execute
        tool_args: Arguments extracted from the LLM's function call

    Returns:
        Dict with at least {'success': bool, 'message': str}
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        logger.warning("Unknown tool requested: %s", tool_name)
        return {"success": False, "message": f"No conozco la herramienta '{tool_name}'."}

    logger.info("Executing tool '%s' for user %s: %s", tool_name, user_id[:8], tool_args)
    try:
        result = await handler(session, user_id, tool_args)
        return result
    except Exception as exc:
        logger.exception("Tool '%s' failed: %s", tool_name, exc)
        return {"success": False, "message": "Tuve un error. ¿Intentamos de nuevo?"}


