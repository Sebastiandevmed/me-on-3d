# Capturas que faltan de PipeBot

Guarda aquí los PNG/JPG con estos nombres exactos. No hace falta que estén todas
para arrancar: el caso de estudio se arma en este orden de prioridad.

| # | Archivo | Qué tiene que verse | Dónde |
|---|---|---|---|
| 1 | `dashboard-pedidos.png` | Dashboard completo: las 4 tarjetas de métricas arriba (conversaciones hoy / pendientes / confirmados / cancelados) + la lista de pedidos con la pestaña **Pendientes** activa | `dashboard/index.html` |
| 2 | `dashboard-chat.png` | El panel derecho con una conversación abierta: burbujas del cliente y del bot, la píldora de estado y el botón de tomar la conversación | mismo, tras clic en un pedido |
| 3 | `dashboard-humano.png` | La MISMA conversación con el humano al mando (`human_active`): se ve que el bot está en pausa | mismo, tras tomar la conversación |
| 4 | `empaque.png` | La pantalla de empaque con tarjetas de pedido y sus ítems | `dashboard/packing.html` |
| 5 | `whatsapp-chat.jpg` | Un chat real de WhatsApp con el bot: saludo, pedido y confirmación. Sirve captura del celular | tu teléfono o WhatsApp Web |
| 6 | `dashboard-movil.png` | (opcional) El dashboard en pantalla angosta, si responde bien | mismo, ventana estrecha |

## Datos sensibles

Tapa o cambia antes de mandar: teléfonos completos, direcciones exactas y apellidos
de clientes reales. Nombres de pila y nombres de negocio pueden quedarse — le dan
verdad al caso. Si prefieres, mándalas tal cual y yo las difumino antes de que entren
a la landing.

## Qué necesitas para levantarlo

- **Dashboard (capturas 1-4):** solo Supabase. Falta `dashboard/config.js` con la URL
  del proyecto y la anon key, y un usuario para `login.html`. Twilio y los LLM NO
  hacen falta para ver los datos que ya están en la base.
- **WhatsApp (captura 5):** nada, es una captura de tu teléfono.
