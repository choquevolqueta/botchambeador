"""
bot_chambeador_ai.py
--------------------
Selenium bot para postular a empleos en computrabajo.cl
con ayuda de IA para encontrar elementos en pantalla y
evaluar ofertas de trabajo.

Swapea la función `llamar_ia()` por la API que prefieras.
"""

import os
import time
import json
import logging
from datetime import datetime
from groq import Groq, RateLimitError
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ------------------------------------------------------------------
# 0. LOGGING
# ------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
LOG_FILE = f"logs/bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),  # también en terminal
    ]
)
log = logging.getLogger("bot")

# ------------------------------------------------------------------
# 0. CONFIGURACIÓN — se carga desde config.json y perfil.json
# ------------------------------------------------------------------
with open("config.json", encoding="utf-8") as f:
    CONFIG = json.load(f)

with open("perfil.json", encoding="utf-8") as f:
    PERFIL = json.load(f)

GROQ_API_KEY = CONFIG["groq_api_key"]
PAIS         = CONFIG["pais"]
BUSQUEDA     = CONFIG["busqueda"]
MAX_OFERTAS  = CONFIG.get("max_ofertas", 15)

URL_CANDIDATOS = f"https://candidato.{PAIS}.computrabajo.com"
URL_BUSQUEDA   = f"https://{PAIS}.computrabajo.com"

CRITERIOS_IA = (
    f"Busco trabajo como {BUSQUEDA}. "
    f"Mis habilidades son: {', '.join(PERFIL.get('habilidades', []))}."
)

# ------------------------------------------------------------------
# 1. CLIENTE DE IA (DUMMY — cambia esto por la API que prefieras)
# ------------------------------------------------------------------
# Cliente Groq compartido (evita crear SSL context en cada llamada)
_groq_client: Groq | None = None
_rate_limit_hit = False   # flag: si True, omitir llamadas IA para no crashear


def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def llamar_ia(prompt_texto: str) -> str:
    """
    Llama a Groq con el prompt dado. Si se excede el límite diario de tokens
    activa el flag _rate_limit_hit y lanza la excepción para que el caller decida.
    """
    global _rate_limit_hit
    if _rate_limit_hit:
        raise RateLimitError("Límite diario alcanzado", response=None, body=None)  # type: ignore

    try:
        respuesta = _get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_texto}],
            max_tokens=300,
        )
        return respuesta.choices[0].message.content.strip()
    except RateLimitError as e:
        msg = str(e)
        if "tokens per day" in msg or "TPD" in msg:
            _rate_limit_hit = True
            log.warning("  [GROQ] Límite diario de tokens alcanzado. Las llamadas IA se omitirán.")
        else:
            log.warning(f"  [GROQ] Rate limit temporal: {msg[:120]}")
        raise


def _ia_si_no(pregunta: str) -> bool:
    """Pregunta rápida de Sí/No a la IA con prompt mínimo (ahorra tokens)."""
    habilidades = ", ".join(PERFIL.get("habilidades", []))
    prompt = (
        f"Candidato: {PERFIL.get('nombre','')}, {PERFIL.get('estudios',[{}])[0].get('titulo','')}, "
        f"habilidades: {habilidades}.\n"
        f"Pregunta del formulario: '{pregunta}'\n"
        "¿Debería responder SÍ? Responde SOLO con SI o NO."
    )
    try:
        return llamar_ia(prompt).strip().upper().startswith("SI")
    except Exception:
        return True  # default: sí


# ------------------------------------------------------------------
# 2. UTILIDADES
# ------------------------------------------------------------------

def ia_evalua_oferta(titulo: str, descripcion: str) -> bool:
    """
    Le pide a la IA que evalúe si una oferta es relevante según CRITERIOS_IA.
    Devuelve True si hay que postular. Si no hay cuota IA disponible, postula igual.
    """
    prompt = (
        f"Criterios del candidato: {CRITERIOS_IA}\n\n"
        f"Oferta:\nTítulo: {titulo}\nDescripción: {descripcion[:400]}\n\n"
        "¿Debería postular? Responde SOLO 'SI' o 'NO' y máximo 15 palabras de razón."
    )
    try:
        return llamar_ia(prompt).strip().upper().startswith("SI")
    except RateLimitError:
        log.warning("  [GROQ] Sin cuota — postulando igual.")
        return True



# ------------------------------------------------------------------
# 3. DRIVER
# ------------------------------------------------------------------
def iniciar_driver() -> webdriver.Chrome | None:
    log.info("Iniciando Chrome...")
    service = ChromeService(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("disable-infobars")
    options.add_argument("start-maximized")

    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(5)
        return driver
    except Exception as e:
        log.error(f"No se pudo iniciar el driver: {e}")
        return None


# ------------------------------------------------------------------
# 4. LOGIN MANUAL
# ------------------------------------------------------------------
def esperar_login_manual(driver: webdriver.Chrome) -> bool:
    log.info(f"Abriendo {URL_CANDIDATOS}...")
    driver.get(URL_CANDIDATOS)

    print("\n" + "="*55)
    print("  Inicia sesion manualmente en el navegador.")
    print("  Cuando veas tu perfil/CV, presiona ENTER.")
    print("="*55)
    input("\n  >> ENTER cuando hayas iniciado sesion... ")

    url_actual = driver.current_url
    log.info(f"URL post-login: {url_actual}")
    if f"candidato.{PAIS}" in url_actual:
        log.info("Sesion detectada, el bot toma el control.")
        return True
    else:
        log.warning(f"No se detecto sesion clara, continuando igual. URL: {url_actual}")
        return True


# ------------------------------------------------------------------
# 5. BÚSQUEDA Y POSTULACIÓN
# ------------------------------------------------------------------
def obtener_urls_ofertas(driver: webdriver.Chrome, busqueda: str) -> list[str]:
    log.info(f"Buscando '{busqueda}'...")
    driver.get(URL_BUSQUEDA)
    time.sleep(2)

    campo = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "prof-cat-search-input"))
    )
    campo.clear()
    campo.send_keys(busqueda)
    time.sleep(1)
    driver.find_element(By.ID, "search-button").click()
    time.sleep(3)

    log.info(f"URL de resultados: {driver.current_url}")

    urls = []
    for link in driver.find_elements(By.TAG_NAME, "a"):
        href = link.get_attribute("href") or ""
        if "/ofertas-de-trabajo/" in href and href not in urls:
            urls.append(href)

    log.info(f"Encontradas {len(urls)} ofertas.")
    return urls[:MAX_OFERTAS]


def generar_respuesta_ia(pregunta: str, titulo_oferta: str) -> str:
    """Usa Groq + el perfil para generar una respuesta personalizada a una pregunta abierta."""
    perfil_str = json.dumps(PERFIL, ensure_ascii=False, indent=2)
    prompt = (
        f"Eres un candidato postulando al cargo '{titulo_oferta}'.\n"
        f"Tu perfil personal es:\n{perfil_str}\n\n"
        f"Responde esta pregunta del formulario de postulacion de forma breve, natural y en primera persona (max 3 oraciones):\n"
        f"Pregunta: {pregunta}\n"
        f"Responde SOLO con la respuesta, sin introduccion ni explicacion."
    )
    return llamar_ia(prompt)


def _respuesta_directa(texto: str) -> str | None:
    """Devuelve respuesta desde el perfil si la pregunta es conocida, o None."""
    t = texto.lower()
    if any(p in t for p in ["presencial", "modalidad", "hibrido", "remoto"]):
        return PERFIL.get("modalidad_preferida", "presencial o híbrida")
    if any(p in t for p in ["disponibilidad", "disponible"]):
        return PERFIL.get("disponibilidad", "inmediata")
    if any(p in t for p in ["renta", "sueldo", "pretension", "expectativa"]):
        return PERFIL.get("expectativa_sueldo", "a convenir")
    if any(p in t for p in ["licencia", "conducir"]):
        return "no"
    if any(p in t for p in ["telefono", "celular", "fono"]):
        return PERFIL.get("telefono", "")
    if any(p in t for p in ["comuna", "sector"]):
        return PERFIL.get("comuna", "Santiago")
    if any(p in t for p in ["ciudad", "ubicacion"]):
        return PERFIL.get("ciudad", "Santiago")
    return None


def _click_radio(driver: webdriver.Chrome, radios: list, respuesta: str, pregunta_txt: str):
    """Elige y hace click en el radio button más adecuado según la respuesta."""
    resp_lower = respuesta.strip().lower()
    es_positivo = any(p in resp_lower for p in ["sí", "si", "yes", "tengo", "cuento", "he ", "experiencia", "inmediata"])

    elegido = None
    for radio in radios:
        radio_id  = radio.get_attribute("id") or ""
        radio_val = (radio.get_attribute("value") or "").lower()
        radio_lbl = ""
        try:
            radio_lbl = driver.find_element(By.CSS_SELECTOR, f"label[for='{radio_id}']").text.lower()
        except Exception:
            pass
        texto_radio = radio_val + " " + radio_lbl
        if es_positivo and any(p in texto_radio for p in ["si", "sí", "yes", "1", "true"]):
            elegido = radio
            break
        if not es_positivo and any(p in texto_radio for p in ["no", "0", "false"]):
            elegido = radio
            break

    if elegido is None:
        elegido = radios[0]

    driver.execute_script("arguments[0].click();", elegido)
    log.info(f"  Radio clickeado ({'SI' if es_positivo else 'NO'}): '{pregunta_txt[:60]}'")


def _label_para(driver: webdriver.Chrome, elemento) -> str:
    """Intenta obtener el texto de pregunta asociado a un campo de formulario."""
    elem_id = elemento.get_attribute("id") or ""
    # 1. label[for=id]
    if elem_id:
        try:
            return driver.find_element(By.CSS_SELECTOR, f"label[for='{elem_id}']").text.strip()
        except Exception:
            pass
    # 2. label hermano previo en el mismo padre
    try:
        parent = elemento.find_element(By.XPATH, "..")
        labels = parent.find_elements(By.CSS_SELECTOR, "label, legend, p")
        if labels:
            return labels[0].text.strip()
    except Exception:
        pass
    # 3. placeholder / name como fallback
    return elemento.get_attribute("placeholder") or elemento.get_attribute("name") or ""


def manejar_formulario_postulacion(driver: webdriver.Chrome, titulo_oferta: str) -> bool:
    """
    Detecta y responde preguntas del formulario de postulacion.
    Trata cada tipo de campo por separado para evitar confusiones:
      - input[type=radio]  → agrupados por atributo 'name'
      - textarea           → respuesta de texto larga
      - input[type=text/number/tel] → respuesta corta
      - select             → elige opción con IA
    """
    time.sleep(2)

    # ¿Hay algún campo de formulario visible?
    todos_campos = driver.find_elements(
        By.CSS_SELECTOR,
        "input:not([type='hidden']):not([type='submit']):not([type='button']), textarea, select"
    )
    campos_visibles = [c for c in todos_campos if c.is_displayed()]
    if not campos_visibles:
        return True

    log.info(f"  Formulario detectado ({len(campos_visibles)} campo/s visible/s).")
    respondidos = 0

    # ── 1. RADIO BUTTONS (agrupados por name) ──────────────────────
    names_vistos: set[str] = set()
    for radio in driver.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
        if not radio.is_displayed():
            continue
        name = radio.get_attribute("name") or ""
        if not name or name in names_vistos:
            continue
        names_vistos.add(name)

        radios_grupo = driver.find_elements(By.CSS_SELECTOR, f"input[type='radio'][name='{name}']")

        # Texto de la pregunta: buscar legend en el fieldset más cercano
        pregunta_txt = ""
        try:
            fs = radio.find_element(By.XPATH, "ancestor::fieldset[1]")
            legends = fs.find_elements(By.CSS_SELECTOR, "legend")
            if legends:
                pregunta_txt = legends[0].text.strip()
        except Exception:
            pass

        if not pregunta_txt:
            pregunta_txt = _label_para(driver, radio)

        log.info(f"  Radio '{name}': '{pregunta_txt[:60]}'")

        respuesta = _respuesta_directa(pregunta_txt)
        if respuesta is None:
            es_si = _ia_si_no(pregunta_txt)
            respuesta = "sí" if es_si else "no"

        _click_radio(driver, radios_grupo, respuesta, pregunta_txt)
        respondidos += 1

    # ── 2. TEXTAREAS ───────────────────────────────────────────────
    for textarea in driver.find_elements(By.CSS_SELECTOR, "textarea"):
        if not textarea.is_displayed():
            continue

        pregunta_txt = _label_para(driver, textarea)
        log.info(f"  Textarea: '{pregunta_txt[:60]}'")

        respuesta = _respuesta_directa(pregunta_txt)
        if respuesta is None:
            try:
                respuesta = generar_respuesta_ia(pregunta_txt or "Cuéntanos sobre ti", titulo_oferta)
                log.info(f"  Respuesta IA: '{respuesta[:80]}'")
            except RateLimitError:
                respuesta = "Disponible de inmediato, con experiencia en marketing digital y creación de contenido."
            except Exception as e:
                log.warning(f"  No se pudo generar respuesta: {e}")
                respuesta = "Disponible de inmediato, con experiencia en el área."

        textarea.clear()
        textarea.send_keys(respuesta)
        log.info(f"  Textarea respondida: '{respuesta[:60]}'")
        respondidos += 1

    # ── 3. INPUTS DE TEXTO / NÚMERO / TEL ─────────────────────────
    for campo in driver.find_elements(
        By.CSS_SELECTOR,
        "input[type='text'], input[type='number'], input[type='tel'], input[type='email']"
    ):
        if not campo.is_displayed():
            continue
        if campo.get_attribute("value"):   # ya tiene valor
            continue

        pregunta_txt = _label_para(driver, campo)
        if not pregunta_txt:
            continue

        log.info(f"  Input texto: '{pregunta_txt[:60]}'")

        respuesta = _respuesta_directa(pregunta_txt)
        if respuesta is None:
            try:
                respuesta = generar_respuesta_ia(pregunta_txt, titulo_oferta)
                log.info(f"  Respuesta IA: '{respuesta[:60]}'")
            except RateLimitError:
                respuesta = ""
            except Exception as e:
                log.warning(f"  No se pudo generar respuesta: {e}")
                respuesta = ""

        if respuesta:
            campo.clear()
            campo.send_keys(respuesta)
            log.info(f"  Input respondido: '{respuesta[:60]}'")
            respondidos += 1

    # ── 4. SELECTS ────────────────────────────────────────────────
    from selenium.webdriver.support.ui import Select as SeleniumSelect
    for select_elem in driver.find_elements(By.CSS_SELECTOR, "select"):
        if not select_elem.is_displayed():
            continue

        pregunta_txt = _label_para(driver, select_elem)
        log.info(f"  Select: '{pregunta_txt[:60]}'")

        sel     = SeleniumSelect(select_elem)
        opciones = [o.text.strip() for o in sel.options if o.text.strip() and o.get_attribute("value")]
        if not opciones:
            continue

        respuesta = None
        texto = pregunta_txt.lower()
        if "disponibilidad" in texto:
            for opt in opciones:
                if "inmediata" in opt.lower():
                    respuesta = opt
                    break

        if not respuesta:
            try:
                opt_str = ", ".join(opciones)
                prompt  = (
                    f"Pregunta: '{pregunta_txt}'\nOpciones: {opt_str}\n"
                    f"Candidato: {PERFIL.get('nombre','')}, {PERFIL.get('estudios',[{}])[0].get('titulo','')}, "
                    f"habilidades: {', '.join(PERFIL.get('habilidades',[])[:4])}.\n"
                    "Elige la opción más adecuada. Responde SOLO con el texto exacto de la opción."
                )
                resp_ia = llamar_ia(prompt).strip()
                for opt in opciones:
                    if resp_ia.lower() in opt.lower() or opt.lower() in resp_ia.lower():
                        respuesta = opt
                        break
            except (RateLimitError, Exception) as e:
                log.warning(f"  Error IA para select: {e}")

        if not respuesta:
            respuesta = opciones[0]

        try:
            sel.select_by_visible_text(respuesta)
            log.info(f"  Select respondido: '{respuesta}'")
            respondidos += 1
        except Exception:
            log.warning(f"  No se pudo seleccionar '{respuesta}'.")

    log.info(f"  Total campos respondidos: {respondidos}")

    # ── Scroll + screenshot + envío ───────────────────────────────
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)

    ruta = f"logs/formulario_{int(time.time())}.png"
    driver.save_screenshot(ruta)
    log.info(f"  Screenshot: {ruta}")

    try:
        candidatos = driver.find_elements(By.XPATH, "//button | //input[@type='submit']")
        enviado = False
        for btn in candidatos:
            if not btn.is_displayed():
                continue
            texto_btn = (btn.text or btn.get_attribute("value") or "").strip().lower()
            if any(p in texto_btn for p in ["enviar", "confirmar", "continuar", "guardar", "postular", "siguiente", "send"]):
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(0.5)
                btn.click()
                log.info(f"  Formulario enviado (boton: '{texto_btn}').")
                enviado = True
                time.sleep(2)
                break

        if not enviado:
            log.warning("  No se encontro boton de envio con texto conocido. Formulario no enviado.")
    except Exception as e:
        log.warning(f"  Error al enviar formulario: {e}")

    return True


def postular_a_oferta(driver: webdriver.Chrome, url: str) -> bool:
    driver.get(url)
    time.sleep(2)

    try:
        titulo = driver.find_element(By.CSS_SELECTOR, "h1").text.strip()
    except Exception:
        titulo = driver.title

    try:
        descripcion = driver.find_element(
            By.CSS_SELECTOR, ".offerDescription, .description, #jobDescription, section p"
        ).text
    except Exception:
        descripcion = titulo

    log.info(f"Oferta: '{titulo[:70]}'")

    if not ia_evalua_oferta(titulo, descripcion):
        log.info("  [IA] No relevante, saltando.")
        return False

    log.info("  [IA] Relevante, postulando...")

    # Verificar si ya se postuló (el botón no existe o dice "Postulado")
    try:
        ya_postulado = driver.find_element(By.XPATH, "//*[contains(text(),'Ya postulaste') or contains(text(),'Postulado') or contains(text(),'Ya te postulaste')]")
        if ya_postulado.is_displayed():
            log.info("  Ya postulado anteriormente, saltando.")
            return False
    except Exception:
        pass  # no existe el mensaje, seguimos normal

    try:
        btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-href-offer-apply]"))
        )
        url_postulacion = btn.get_attribute("data-href-offer-apply")
        log.info(f"  URL postulacion: {url_postulacion}")
        btn.click()
        time.sleep(3)

        log.info(f"  URL tras click: {driver.current_url}")

        # Manejar formulario si aparece
        manejar_formulario_postulacion(driver, titulo)

        if "match" in driver.current_url or "candidato" in driver.current_url:
            log.info(f"  [OK] Postulado exitosamente: {titulo[:55]}")
        else:
            log.info(f"  [OK] Click enviado: {titulo[:55]}")

        driver.save_screenshot(f"logs/postulacion_ok_{int(time.time())}.png")
        return True

    except Exception as e:
        log.error(f"  No se pudo postular: {e}")
        driver.save_screenshot(f"logs/postulacion_error_{int(time.time())}.png")
        return False


def buscar_y_postular(driver: webdriver.Chrome, busqueda: str):
    urls = obtener_urls_ofertas(driver, busqueda)
    if not urls:
        log.warning("No se encontraron ofertas.")
        return

    postuladas = 0
    for i, url in enumerate(urls, 1):
        log.info(f"--- Oferta {i}/{len(urls)} ---")
        if postular_a_oferta(driver, url):
            postuladas += 1
        time.sleep(2)

    log.info(f"RESUMEN: {postuladas} postulaciones enviadas de {len(urls)} ofertas revisadas.")
    log.info(f"Log guardado en: {LOG_FILE}")


# ------------------------------------------------------------------
# 6. MAIN
# ------------------------------------------------------------------
if __name__ == "__main__":
    log.info(f"=== Bot iniciado | Log: {LOG_FILE} ===")
    driver = iniciar_driver()

    if driver:
        try:
            if esperar_login_manual(driver):
                buscar_y_postular(driver, BUSQUEDA)
            else:
                log.error("No se detecto sesion activa.")
        finally:
            log.info("Cerrando navegador...")
            time.sleep(3)
            driver.quit()
