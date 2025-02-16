import os, asyncio
from dotenv import load_dotenv

# Cargar variables de entorno (para API keys y otros datos sensibles opcionales)
load_dotenv()

# Importar clases de BrowserUse y modelos de lenguaje
from browser_use import Browser, Agent, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

# --- Configuración general ---

# Modo headless vs visible
HEADLESS_MODE = False  # Cambiar a True para ejecutar en segundo plano sin ventana gráfica

# Configurar el directorio de descarga de archivos (PDF) al directorio actual del script
download_dir = os.getcwd()
context_config = BrowserContextConfig(
    save_downloads_path=download_dir,
    disable_security=True,
    
    # Establecer un User-Agent común de Chrome en Windows para evitar detección
    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/117.0.5938.62 Safari/537.36"),
               
               
)

# Crear instancia de navegador con la configuración deseada
browser = Browser(config=BrowserConfig(headless=HEADLESS_MODE, disable_security=False, 
                                       new_context_config=context_config))
# Crear contexto de navegador (pestaña) con la configuración de descargas y UA
context = BrowserContext(browser=browser, config=context_config)

# Preparar el modelo de lenguaje (LLM) - Google Gemini 2.0 (flash-exp) en este caso
# Se espera que la API Key de Gemini esté definida en la variable de entorno GEMINI_API_KEY
gemini_api_key = os.getenv("GEMINI_API_KEY")
llm = ChatGoogleGenerativeAI(
    model='gemini-2.0-flash',
    api_key=SecretStr(gemini_api_key) if gemini_api_key else None
)
# (Nota: Si no se cuenta con acceso a Gemini, se podría usar un modelo de OpenAI:
#   from langchain_openai import ChatOpenAI
#   llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
# y asegurar que OPENAI_API_KEY esté en el .env)

# Credenciales de acceso al portal (NIT y clave) marcadas como datos sensibles
NIT = "06142203231076"
CLAVE = "Eet7jPy9qB"
sensitive_data = {
    'x_nit': NIT,
    'x_pass': CLAVE
}
# (Alternativamente, por seguridad podría leerse de os.getenv('DGII_NIT') y os.getenv('DGII_CLAVE'))

# Definir la tarea de navegación en lenguaje natural que el agente (LLM) debe realizar
task_description = (
    "Inicia sesión en https://portaldgii.mh.gob.sv/ssc/home con NIT x_nit y clave x_pass. "
    "Después de ingresar, haz clic en 'Peticiones y Estado de Cuenta Tributario'. "
    "Luego selecciona 'Solicitud e Impresión de Solvencia o Estado de Cuenta'. "
    "Si el estado tributario mostrado es 'SOLVENTE', haz clic en 'IMPRIMIR CONSTANCIA'. "
    "Espera a que se genere la constancia. Descarga el pdf que se te muestra en pantalla."
)
# (La instrucción incluye los placeholders x_nit y x_pass que serán reemplazados 
#  por los valores reales definidos en sensitive_data, manteniendo seguros los datos.)

# Crear el agente de automatización con el navegador, la tarea y el modelo LLM
agent = Agent(
    browser_context=context,
    task=task_description,
    llm=llm,
    sensitive_data=sensitive_data
)

# --- Ejecución de la tarea asincrónica ---
async def run_automation():
    try:
        # Ejecutar la secuencia de instrucciones en el navegador
        result = await agent.run()
        # (El resultado 'result' puede contener un resumen o mensaje final del agente, si es necesario usarlo.)

        # Capturar pantalla de la página de confirmación (estado tributario) antes de cerrar nada
        
        page = await agent.browser_context.get_current_page()
        await page.screenshot(path="estado_tributario.png")
        print("Captura de pantalla guardada: estado_tributario.png")

        # await page.pdf(path="ConstanciaSolvencia.pdf")

    # Intentamos capturar la descarga del PDF usando el evento 'expect_download'
        async with page.expect_download() as download_info:
            # Aquí forzamos el click en "IMPRIMIR CONSTANCIA" si el agente no lo ha hecho aún.
            await page.click("text='IMPRIMIR CONSTANCIA'")
                
        # Este bloque se ejecuta cuando Playwright detecta la descarga
        download = await download_info.value
        path = await download.path()
        print("Se descargó el archivo en:", path)

        # Guardar/renombrar el PDF
        pdf_name = "ConstanciaSolvencia.pdf"
        await download.save_as(os.path.join(download_dir, pdf_name))
        print(f"PDF guardado como: {pdf_name}")

        # Si quieres verificar si se guardó:
        if os.path.exists(os.path.join(download_dir, pdf_name)):
            print("Descarga verificada correctamente.")
        else:
            print("El PDF no se encontró en el directorio de descargas.")

        # Este bloque se ejecuta cuando Playwright detecta la descarga
        download = await download_info.value
        path = await download.path()
        print("Se descargó el archivo en:", path)

        # Esperar unos segundos para asegurar que la descarga del PDF se complete
        await asyncio.sleep(5)
        # Verificar si el archivo PDF fue descargado
        for fname in os.listdir(download_dir):
            if fname.lower().endswith(".pdf"):
                print(f"PDF de solvencia descargado: {fname}")
                # Opcional: renombrar el archivo a un nombre más descriptivo
                # os.rename(os.path.join(download_dir, fname), os.path.join(download_dir, "ConstanciaSolvencia.pdf"))
                break

        # Cerrar sesión en el portal (si corresponde) - podría hacerse navegando a la opción "Salir"
        # En caso de no encontrar botón de salir, simplemente cerramos el navegador.
        # Intentar encontrar y hacer clic en "Salir" o "Cerrar Sesión"
        try:
            logout_button = await page.query_selector("text='Salir'")  # Buscar elemento por texto visible
            if logout_button:
                await logout_button.click()
                print("Se cerró sesión en el portal.")
        except Exception as e:
            pass  # Si no se encuentra el botón o falla, continuar con cierre de navegador

    finally:
        # Cerrar el navegador por completo
        await browser.close()
        print("Navegador cerrado. Proceso completo.")

# Ejecutar la rutina de automatización de forma asíncrona
asyncio.run(run_automation())
