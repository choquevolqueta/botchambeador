# Bot Chambeador AI

Bot que automatiza postulaciones en [Computrabajo](https://computrabajo.com) usando Selenium + IA (Groq). Busca ofertas según tu perfil, evalúa si son relevantes y completa los formularios de postulación automáticamente.

---

## Requisitos

- Python 3.10 o superior
- Google Chrome instalado
- Una cuenta en [Computrabajo](https://computrabajo.com)
- Una API key de [Groq](https://console.groq.com) (gratuita)

---

## Terminal recomendada (Windows)

Los comandos de este proyecto se ejecutan desde una consola. En Windows tienes varias opciones:

| Terminal | Cómo abrirla |
|---|---|
| **MinGW64 / Git Bash** | Click derecho en la carpeta del proyecto → "Git Bash Here" |
| **PowerShell** | Presiona `Win + R`, escribe `powershell`, ENTER. Luego navega con `cd` |
| **CMD** | Presiona `Win + R`, escribe `cmd`, ENTER. Luego navega con `cd` |

> Si no tienes ninguna, instala [Git para Windows](https://git-scm.com/download/win) — incluye Git Bash (MinGW64).

Una vez abierta la terminal, asegúrate de estar en la carpeta del proyecto. Debería verse algo así:

```
usuario@PC MINGW64 ~/Documents/bot-chamba
$
```

Si no, navega con:

```bash
cd "ruta/a/la/carpeta/del/bot"
```

---

## Instalación

```bash
pip install -r requirements.txt
```

---

## Configuración

Antes de correr el bot, edita los dos archivos de configuración:

### `config.json`

```json
{
    "groq_api_key": "TU_API_KEY_DE_GROQ",
    "pais": "cl",
    "busqueda": "marketing digital",
    "max_ofertas": 20
}
```

| Campo | Descripción |
|---|---|
| `groq_api_key` | Tu API key de Groq. Obtenla en console.groq.com |
| `pais` | Código del país: `cl` Chile, `pe` Perú, `ar` Argentina, etc. |
| `busqueda` | Término de búsqueda de empleos |
| `max_ofertas` | Cuántas ofertas revisar por sesión |

### `perfil.json`

Completa con tus datos reales. El bot usa esta información para:
- Responder preguntas de los formularios de postulación
- Que la IA evalúe si una oferta es relevante para tu perfil

```json
{
    "nombre": "Tu Nombre",
    "edad": 25,
    "ciudad": "Santiago",
    "comuna": "Providencia",
    "telefono": "+56912345678",
    "email": "tu_email@ejemplo.com",
    "experiencia": [...],
    "estudios": [...],
    "habilidades": [...],
    ...
}
```

---

## Uso

### Correr el bot

```bash
python bot_chambeador_ai.py
```

El bot va a:
1. Abrir Chrome
2. Navegar a Computrabajo y esperar que **inicies sesión manualmente** Tienes que iniciar sesion manualmente, recomiendo que te crees una cuenta aparte en Computrabajo, solo porsiacaso, igual si quieres usar la de siempre no hay problema, igual es indiferente si te logeas mediante una cuenta de google, pero tendras que iniciar sesion con tu cuenta de Google en el navegador.
3. Tienes que volver a la consola y presionar enter para que el bot tome el control nuevamente.
4. Busca ofertas según `config.json`
5. Por cada oferta, la IA evalúa si es relevante para tu perfil
6. Si es relevante, postula y completa el formulario

> El login es manual a propósito para evitar bloqueos por automatización.

---

## Archivos generados

Después de correr el bot encontrarás:

```
logs/
├── bot_YYYYMMDD_HHMMSS.log     ← registro completo de la sesión
└── formulario_*.png            ← screenshot de cada formulario completado
```

---

## Depuración

Si el bot no encuentra ofertas o falla al postular, usa el script de diagnóstico:

```bash
python debug_explorador.py
```

Este script **no postula nada**. Solo navega el sitio paso a paso y guarda screenshots + HTML en `debug_capturas/` para que puedas ver qué está pasando.

---

## Límites de la API de Groq

Groq tiene un límite diario de tokens en el plan gratuito. Si el bot lo alcanza:
- Muestra el aviso `[GROQ] Límite diario de tokens alcanzado`
- Sigue postulando sin evaluación IA (postula a todo)

Puedes aumentar el límite cambiando a un plan pago o usando otro proveedor compatible con la API de OpenAI (OpenRouter, Together.ai, etc.) modificando la función `llamar_ia()` en el script.

---

## Estructura del proyecto

```
bot_chambeador_ai.py    ← script principal
debug_explorador.py     ← script de diagnóstico (no postula)
config.json             ← configuración (API key, país, búsqueda)
perfil.json             ← tu perfil profesional
requirements.txt        ← dependencias Python
```
