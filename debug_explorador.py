"""
debug_explorador.py
-------------------
Script de exploración de computrabajo.cl.
NO postula a nada — solo captura screenshots y HTML en cada paso
para entender cómo funciona el sitio.

Uso:
    python debug_explorador.py
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

PAIS      = "cl"
URL_LOGIN = f"https://candidato.{PAIS}.computrabajo.com"
URL_BASE  = f"https://{PAIS}.computrabajo.com"
BUSQUEDA  = "asistente de marketing"
CARPETA   = "debug_capturas"

os.makedirs(CARPETA, exist_ok=True)


def guardar_paso(driver, nombre: str):
    """Guarda screenshot + HTML del estado actual del navegador."""
    ruta_img  = os.path.join(CARPETA, f"{nombre}.png")
    ruta_html = os.path.join(CARPETA, f"{nombre}.html")
    driver.save_screenshot(ruta_img)
    with open(ruta_html, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"   [Guardado] {ruta_img} + {ruta_html}")


def iniciar_driver():
    service = ChromeService(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("disable-infobars")
    options.add_argument("start-maximized")
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(5)
    return driver


if __name__ == "__main__":
    driver = iniciar_driver()

    try:
        # ── PASO 1: Login ─────────────────────────────────────────────
        print(f"\n-> Abriendo {URL_LOGIN}...")
        driver.get(URL_LOGIN)
        time.sleep(2)
        guardar_paso(driver, "01_pagina_inicial")

        print("\n" + "="*55)
        print("  Inicia sesion manualmente en el navegador.")
        print("  Espera a que la pagina cambie a tu perfil/CV.")
        print("  RECIEN AHI vuelve aqui y presiona ENTER.")
        print("="*55)
        input("\n  >> ENTER cuando veas tu perfil en el navegador... ")

        url_actual = driver.current_url
        print(f"\n-> URL actual: {url_actual}")
        if "secure.computrabajo" in url_actual or "login" in url_actual.lower():
            print("[WARN] Parece que aun estas en el login.")
            input("  >> Presiona ENTER de nuevo cuando estes logueado... ")

        # ── PASO 2: Home post-login ───────────────────────────────────
        print("\n-> Capturando home post-login...")
        time.sleep(1)
        guardar_paso(driver, "02_home_logueado")

        # ── PASO 3: Búsqueda usando el formulario del sitio ───────────
        print(f"\n-> Navegando a {URL_BASE} para usar el buscador...")
        driver.get(URL_BASE)
        time.sleep(2)

        try:
            campo = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "prof-cat-search-input"))
            )
            campo.clear()
            campo.send_keys(BUSQUEDA)
            time.sleep(1)
            driver.find_element(By.ID, "search-button").click()
            time.sleep(3)
            print(f"-> Busqueda enviada. URL resultante: {driver.current_url}")
        except Exception as e:
            print(f"   [WARN] No se pudo usar el formulario ({e})")
            print("   Intentando URL directa...")
            driver.get(f"{URL_BASE}/trabajo/?q={BUSQUEDA.replace(' ', '+')}")
            time.sleep(3)
            print(f"-> URL resultante: {driver.current_url}")

        guardar_paso(driver, "03_resultados_busqueda")

        # Recolectar links de ofertas reales
        print("\n-> Buscando links de ofertas...")
        links = driver.find_elements(By.TAG_NAME, "a")
        ofertas_candidatos = []
        otros_links = []

        for link in links:
            href = link.get_attribute("href") or ""
            texto = link.text.strip()
            if not href or "computrabajo" not in href or not texto:
                continue
            # Patrones comunes de URLs de ofertas en computrabajo
            if any(x in href for x in ["/trabajo-de-", "/oferta-", "-of-", "/empleo-"]):
                print(f"   [OFERTA] {texto[:55]} -> {href[:85]}")
                ofertas_candidatos.append(href)
            else:
                otros_links.append((texto, href))

        if not ofertas_candidatos:
            print("\n   [WARN] No encontre ofertas con patron conocido.")
            print("   Mostrando TODOS los links para analisis:")
            for texto, href in otros_links:
                if len(texto) > 3:
                    print(f"   [{texto[:55]}] -> {href[:85]}")
            # Tomar cualquier link que no sea navegacion
            ofertas_candidatos = [
                href for texto, href in otros_links
                if len(texto) > 10 and href != URL_BASE and "empleos-en-" not in href
                and "empresas" not in href and "salarios" not in href
            ]

        # ── PASO 4: Primera oferta ────────────────────────────────────
        if ofertas_candidatos:
            print(f"\n-> Entrando a la primera oferta: {ofertas_candidatos[0]}")
            driver.get(ofertas_candidatos[0])
            time.sleep(2)
            guardar_paso(driver, "04_detalle_oferta")

            print("\n-> Botones en el detalle de oferta:")
            for btn in driver.find_elements(By.TAG_NAME, "button"):
                print(f"   id='{btn.get_attribute('id')}' | class='{btn.get_attribute('class')}' | texto='{btn.text.strip()}'")

            print("\n-> Links relevantes en la oferta:")
            for link in driver.find_elements(By.TAG_NAME, "a"):
                texto = link.text.strip()
                href  = link.get_attribute("href") or ""
                if any(p in texto.lower() for p in ["postul", "inscrib", "aplicar", "enviar"]):
                    print(f"   [ACCION] id='{link.get_attribute('id')}' | texto='{texto}' | href='{href[:70]}'")

            # ── PASO 5: Click en Postular ─────────────────────────────
            input("\n  >> Presiona ENTER para intentar click en 'Postular'... ")
            try:
                clickeado = False
                # Buscar por texto en botones y links
                for elemento in driver.find_elements(By.XPATH, "//*[self::button or self::a]"):
                    if any(p in (elemento.text or "").lower() for p in ["postul", "inscrib", "aplicar"]):
                        print(f"   Encontre: '{elemento.text}' | tag={elemento.tag_name} | id='{elemento.get_attribute('id')}'")
                        elemento.click()
                        clickeado = True
                        time.sleep(2)
                        guardar_paso(driver, "05_despues_click_postular")

                        print("\n-> Elementos visibles tras el click:")
                        for b in driver.find_elements(By.TAG_NAME, "button"):
                            if b.is_displayed():
                                print(f"   id='{b.get_attribute('id')}' | texto='{b.text.strip()}'")
                        break

                if not clickeado:
                    print("   No encontre boton de postulacion con texto conocido.")
                    guardar_paso(driver, "05_sin_boton_postular")

            except Exception as e:
                print(f"   [ERROR] {e}")
                guardar_paso(driver, "05_error_click_postular")
        else:
            print("\n[WARN] No se encontraron ofertas. Revisa 03_resultados_busqueda.html y .png")

        print(f"\n{'='*55}")
        print(f"  Exploracion completa.")
        print(f"  Archivos en: {CARPETA}/")
        print(f"{'='*55}")

    finally:
        input("\n  >> Presiona ENTER para cerrar el navegador... ")
        driver.quit()
