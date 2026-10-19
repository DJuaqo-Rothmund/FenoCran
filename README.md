# FenoCran · Cuaderno de campo digital para cranberry (*Vaccinium macrocarpon*)

*By DJuaqo, potenciado con Claude AI.*

Aplicación Android (Python + Kivy/KivyMD) para el **seguimiento fenológico y biométrico de ensayos
y predios de cranberry**, pensada para trabajar en terreno **sin conexión** (offline-first).
Es la versión para cranberry de **FenoRubus** (frambueso): misma arquitectura y funciones, con la
escala de estados del *Instructivo de estados fenológicos para el control de heladas*
(IT-AGR-006), camas en lugar de equipos de riego y paleta burdeos / verde oscuro.

* Registro semanal por **Semanas de Muestreo** (la Semana 1 se define en Ajustes; temporada junio-mayo).
* **11 estados fenológicos** con su **criterio de control de helada** (ver sección 7).
* **Registro fotográfico dual** por variedad y semana: canopia/planta completa + detalle/macro
  (cámara o galería).
* **Sugerencia automática del estado fenológico** con IA local (Edge AI) sobre la foto de detalle.
* **Módulo de calibración de la IA protegido por PIN** (`1234` por defecto): documentos técnicos,
  etiquetado de fotos (few-shot k-NN), evaluación y re-entrenamiento.
* Catálogo dinámico de variedades con **parámetros biométricos** y campos personalizados.
* **Recordatorios semanales** (viernes por defecto) con alarmas exactas de Android.
* **Informes HTML autocontenidos** (imágenes en Base64) o **ZIP portátil**, listos para WhatsApp o correo.
* **Vista previa de informes** dentro de la app (pestaña con el ojo): resumen de lo que se
  mostrará (variedades, fotos, estados fenológicos, datos faltantes, tamaño estimado) y visualización
  completa en un WebView nativo, sin enviar ni copiar nada a Descargas.
* **Semana de inicio configurable** (Ajustes): cualquier fecha como Semana 1; por defecto la
  semana del 7 de septiembre, con botón para restablecerla.
* **Fotos en el teléfono:** las tomadas con la cámara de la app quedan en
  *Imágenes › Imágenes de Fenología*, listas para respaldarse con Google Fotos
  (*Biblioteca › Fotos del dispositivo › activar copia*). Nombre de cada foto (igual en el
  teléfono, en la app y en Drive): `ddmmaaaa-<Variedad><G|D>`, con la fecha de inicio de la
  semana de muestreo, la abreviatura de la variedad (su campo «Código / abreviatura») y
  G = general (canopia) o D = detalle; p. ej. `20260928-NV-SteG.jpg`, `20260921-NV-BLD.jpg`.
  Las fotos adicionales del mismo registro llevan `-2`, `-3`…
  En los predios cada unidad es una **cama** (1-300 o más, se escribe el número) con su
  **sector** opcional; se agregan tras el código: `20260928-P1-SteS3C45G` (sector 3, cama 45,
  foto general). La asignación cama → sector es propia de cada predio.
* **Variedades** se administran en *Ajustes (engrane) › Variedades*.
* **Ubicación de la muestra (opcional):** en cada registro, «Mi ubicación» (GPS del teléfono),
  «Marcar en mapa» (OpenStreetMap, pin central; las zonas vistas quedan en caché para usarse
  sin conexión) o automática si la foto trae coordenadas GPS. Aparece en los informes con
  enlace al mapa y se puede importar con las columnas `latitud`/`longitud`.
* **Optimizada para gama media/baja:** tarjetas livianas (sin MDCard), pantallas y módulos
  pesados (numpy, IA, Jinja2) cargados bajo demanda, fotos y miniaturas en segundo plano,
  sin MSAA, SQLite en WAL/NORMAL.
* Trazabilidad: bitácora de cambios (`audit_log`) y respaldo de la base SQLite.

---

## 1. Arquitectura

```
main.py                  Punto de entrada, App KivyMD, navegación, servicios compartidos
database.py              Esquema SQLite + CRUD (variedades, métricas, campos extra, semanas,
                         observaciones, fotos, escala fenológica, referencias IA, documentos, bitácora)
ai_classifier.py         Extractor de características, k-NN coseno, priors agronómicos,
                         calibración (documentos, referencias, evaluación LOO) y PinGuard (PIN 1234)
reporter.py              Generador Jinja2 de los 4 informes HTML (Base64) / ZIP portátil
notifications.py         Recordatorios: AlarmManager exacto -> servicio p4a -> notificación
phenology.py             Estados del cranberry (IT-AGR-006) y heladas, semanas, calendario esperado
android_bridge.py        Cámara (MediaStore), galería (Photo Picker), documentos, compartir, permisos
platform_utils.py        Detección de plataforma y rutas de datos (app y servicio)
service/reminder_service.py   Servicio Android que publica el aviso y re-programa la alarma
ui/layout.kv             Layout KivyMD (estética cranberry: verdes oscuros + burdeos, tarjetas de vidrio)
ui/screens.py            Lógica de pantallas: Muestreo, Variedades, Informes, Vista previa,
                         Ajustes, Registro (variedad × semana), Ficha de variedad, Calibración IA
ui/theme.py              Paleta cranberry, vidrio y colores por estadio
assets/ui/               Iconos de navegación y fondo (generados con tools/make_ui_assets.py)
templates/*.html         Plantillas de informes (CSS responsivo, modo claro/oscuro, impresión)
tools/demo_data.py       Datos de demostración con fotos sintéticas (pruebas en PC)
tools/export_mobilenet_tflite.py   Exportador opcional de MobileNetV3-Small a TFLite
tests/test_core.py       Pruebas del núcleo (pytest)
buildozer.spec           Compilación Android (permisos, servicio, dependencias)
```

### Modelo de datos (SQLite)

| Tabla | Contenido |
|---|---|
| `varieties` | Catálogo (4 variedades iniciales: Stevens, Ben Lear, Pilgrim, Mullica Queen). Archivado suave o eliminación definitiva. |
| `variety_metrics` | Por variedad y temporada: rendimiento histórico, proyección, cañas basales, laterales (con unidades). |
| `custom_fields` | Parámetros llave-valor-unidad (ej. «Diámetro de caña (mm)», «Grados Brix»). |
| `sampling_weeks` | Semana N, fecha de inicio y etiqueta («Semana del 14 de septiembre»). |
| `observations` | Variedad × semana: estado (1-11), sugerencia IA (código, confianza, detalle), aceptada/corregida, notas. |
| `photos` | Foto `canopy` y `detail` por observación (origen cámara/galería, fecha). |
| `bbch_stages` | Escala de estados editable (base + claves importadas de documentos). |
| `ai_references` | Embeddings etiquetados para el k-NN (few-shot). |
| `documents`, `settings`, `audit_log` | Documentos técnicos, preferencias, bitácora. |

### IA local (Edge AI)

1. **Extractor de descriptores** (`HandcraftedExtractor`, solo numpy + Pillow, ~277 dimensiones):
   histogramas HSV (imagen completa y centro), fracciones de colores con sentido agronómico
   (blanco pétalo, rosado, rojo cranberry, verde, pardo, amarillo), HOG simplificado, magnitud de
   gradiente y LBP uniforme (textura de drupéolas y yemas).
   *Opcional:* `TFLiteExtractor` con MobileNetV3-Small (ver sección 5).
2. **k-NN por similitud coseno** sobre la base de referencia que se construye etiquetando fotos reales
   en el módulo de calibración (few-shot learning, sin re-entrenar redes).
3. **Priors agronómicos** combinados en un modelo log-lineal, que permiten sugerir desde el primer día:
   * *temporal*: la variedad no retrocede respecto de su último estado y avanza a la tasa del calendario;
   * *cromático*: flor blanca → 6x, rojo → 8x, pardo → 0x/9x…;
   * *textual*: coincidencia de las notas de campo con las claves de cada estadio (enriquecidas con
     los documentos cargados).

La sugerencia (top-3 + confianza + explicación) se precarga en el campo **editable** de estado
fenológico; el evaluador la acepta o corrige, y la app registra si fue aceptada o corregida.

---

## 2. Ejecutar y probar en PC (escritorio)

Requisitos: Python 3.10 o 3.11.

```bash
git clone <repo> fenocran && cd fenocran
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-desktop.txt

# (opcional) datos de demostración: 4 variedades × 14 semanas con fotos sintéticas
FENOCRAN_DATA=./demo-data python tools/demo_data.py --weeks 14

# ejecutar la app (ventana 412×860, tamaño de teléfono)
FENOCRAN_DATA=./demo-data python main.py      # con datos de demostración
python main.py                                   # base real en ~/.local/share/fenocran

# pruebas del núcleo (BD, semanas, IA, PIN, recordatorios, informes)
pytest -q
```

En Windows (PowerShell) defina la variable con `$env:FENOCRAN_DATA="demo-data"`.

En escritorio no hay cámara integrada: los botones *Cámara* y *Galería* abren un selector de archivos,
los informes se abren en el navegador y los recordatorios se muestran con Plyer mientras la app está abierta.

**Recorrido sugerido:** Muestreo → tocar una variedad → subir la *Foto 2 · Detalle* → ver la sugerencia
BBCH → Guardar. Luego *Vista previa* (ojo) → elegir el tipo de informe → revisar el resumen →
*Ver vista previa completa*. El cerebro de la barra superior abre el entrenador de IA (PIN **1234**)
y el engranaje, los Ajustes.

---

## 3. Compilar el APK con Buildozer

### Opción A — Linux (Ubuntu 22.04 / 24.04 o WSL2)

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv autoconf libtool \
    pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev automake libltdl-dev build-essential \
    ccache lld
python3 -m venv ~/bdenv && source ~/bdenv/bin/activate
pip install --upgrade pip "cython<3.1" buildozer==1.6.0 setuptools

cd fenocran
buildozer -v android debug          # 1ª vez: 20-40 min (descarga SDK/NDK y compila numpy/pillow)
# resultado: bin/fenocran-1.0.0-arm64-v8a-debug.apk  (teléfonos de 64 bits)
```

Instalar en un teléfono conectado por USB (con depuración USB activada):

```bash
buildozer android deploy run logcat | grep -iE "python|fenocran"
# o bien:  adb install -r bin/*.apk
```

### Opción B — Google Colab

```python
# Celda 1: dependencias del sistema
!sudo apt-get update -qq
!sudo apt-get install -y -qq openjdk-17-jdk autoconf libtool pkg-config zlib1g-dev \
    libncurses-dev cmake libffi-dev libssl-dev automake libltdl-dev zip unzip lld > /dev/null
!pip install -q "cython<3.1" buildozer==1.6.0 setuptools
```

```python
# Celda 2: código fuente (clonar el repo o subir un .zip del proyecto)
!git clone https://github.com/DJuaqo-Rothmund/appdatacration.git
%cd appdatacration
# alternativa: from google.colab import files; files.upload()  y luego  !unzip -o proyecto.zip
```

```python
# Celda 3: compilar (Colab corre como root; buildozer.spec ya trae warn_on_root = 0)
!yes | buildozer -v android debug
```

```python
# Celda 4: descargar el APK
from google.colab import files
import glob
files.download(glob.glob("bin/*.apk")[0])
```

> Si la sesión de Colab se reinicia se pierde `.buildozer/`; para compilaciones repetidas conviene
> montar Google Drive y trabajar dentro de `/content/drive/MyDrive/...`.

### Versión de lanzamiento (firmada)

```bash
buildozer android release           # genera .aab (android.release_artifact = aab)
# Firmar con su keystore: variables P4A_RELEASE_KEYSTORE, P4A_RELEASE_KEYSTORE_PASSWD,
# P4A_RELEASE_KEYALIAS, P4A_RELEASE_KEYALIAS_PASSWD
```

---

## 4. Permisos y comportamiento en Android

| Permiso | Uso |
|---|---|
| `CAMERA` | Captura directa (la foto se escribe vía MediaStore en *Imágenes/FenoCran* y se copia al almacenamiento privado). |
| `READ_MEDIA_IMAGES` (13+), `READ/WRITE_EXTERNAL_STORAGE` (≤12 / ≤9) | Galería y guardado local. En Android 13+ se usa el *Photo Picker* del sistema. |
| `POST_NOTIFICATIONS` | Aviso semanal (se solicita al iniciar en Android 13+). |
| `SCHEDULE_EXACT_ALARM`, `USE_EXACT_ALARM`, `WAKE_LOCK` | Alarma exacta aun en modo Doze. |
| `FOREGROUND_SERVICE` | Servicio `Reminder` (tipo `shortService`) que publica el aviso con la app cerrada. |

* Si el sistema revoca las alarmas exactas, *Ajustes* muestra **«Permitir alarmas exactas»**, que abre el
  ajuste del sistema. **Quite `USE_EXACT_ALARM` si va a publicar en Google Play.**
* Android borra las alarmas al reiniciar el teléfono: la app las vuelve a programar cada vez que se abre.
* Los informes se copian a *Descargas/FenoCran* y se comparten con el menú del sistema (WhatsApp, Gmail, Drive…).

---

## 4a. Actualizar la app sin desinstalar

Android instala un APK encima del anterior (conservando todos los datos) solo si:

1. **Mismo paquete**: `org.cran.fenocran` (no cambiar `package.name` / `package.domain`).
2. **Misma firma**: CI firma siempre con `android/debug.keystore` del repositorio.
   **No borrar ni regenerar ese archivo**: con otra clave habría que desinstalar.
3. **Versión igual o mayor**: CI numera cada compilación `1.1.<n.º de ejecución>`
   (visible en *Ajustes › Trazabilidad y datos*).

Para actualizar: descargar el APK nuevo, abrirlo y tocar **Actualizar**.

## 4b. Respaldo de fotos en Google Drive

Cada foto nueva queda en el teléfono (carpeta «Imágenes de Fenología» para las de
la cámara) **y** se encola para subirse a *Mi unidad › FenoCran · Imágenes de
Fenología › Temporada AAAA-AAAA › Semana NN · dd-mm-aaaa*. Sin señal, la cola se guarda en SQLite y se sube
sola al volver la conexión (por defecto solo con Wi-Fi; se cambia en Ajustes).
La app pide el permiso mínimo `drive.file`: solo ve los archivos que ella creó.

Los informes se pueden subir desde el menú del informe («Guardar en Google Drive»): los
semanales a la carpeta de su semana y el resto a «Temporada … › Informes».

Configuración única (Google exige registrar la app, gratis):

1. En <https://console.cloud.google.com> cree un proyecto y habilite **Google Drive API**.
2. *Pantalla de consentimiento OAuth*: tipo **Externo**, estado *Prueba*, y agregue su
   correo en **Usuarios de prueba**.
3. *Credenciales › Crear ID de cliente OAuth › Android*:
   - Nombre del paquete: `org.cran.fenocran`
   - Huella SHA-1 (clave de firma del repo `android/debug.keystore`, la usa CI):
     `ED:B0:58:5C:E0:94:DF:75:D4:79:D5:47:C1:0C:C0:81:0E:F0:40:38`
4. En la app: **Ajustes (engrane) › Respaldo en Google Drive › Conectar Google Drive**,
   elija la cuenta y acepte. «Subir anteriores» respalda las fotos ya existentes.

Si compila con otra clave (por ejemplo una de lanzamiento), registre también su SHA-1:
`keytool -list -v -keystore su.keystore`.

## 5. (Opcional) Extractor MobileNetV3 con TFLite

```bash
pip install tensorflow
python tools/export_mobilenet_tflite.py      # crea assets/models/*.tflite y model.json
```

Agregue `tflite-runtime` a `requirements` en `buildozer.spec` y recompile. La app detecta el modelo
automáticamente; en *Calibración IA → Modelo → Re-entrenar* se recalculan las referencias con el nuevo
extractor. Sin el modelo, la app usa el extractor liviano de numpy (sin dependencias nativas extra).

---

## 6. Uso del módulo de calibración (PIN `1234`)

* **Documentos:** cargue PDF/TXT con claves fenológicas. Se detectan patrones como
  `5.- ELONGACIÓN…`, `Estado 5: Elongación…` o `5 - …` (solo estados 1-11); los existentes
  se enriquecen con palabras clave (usadas para interpretar las notas de campo).
* **Etiquetado:** toque una foto de detalle y asigne su estado real → se agrega a la base de referencia.
  *Agregar todas las fotos ya etiquetadas* usa los estados confirmados en los registros.
  *Aprendizaje continuo* agrega automáticamente cada registro guardado.
* **Modelo:** referencias por estadio, **validación cruzada leave-one-out** (exactitud por código y por
  estadio principal), re-entrenamiento y cambio de PIN (hash SHA-256 con sal; bloqueo de 30 s tras 5 intentos).

Recomendación: 5-10 fotos de detalle bien etiquetadas por estado (yema apretada, yema blanca,
repollo, gancho, flor, fruta verde, fruta roja…) mejoran notablemente las sugerencias.

---

## 7. Estados fenológicos incluidos (cranberry)

Del *Instructivo de estados fenológicos para el control de heladas* (Agrícola Cran Chile,
IT-AGR-006 v3). El número es el que se registra; la posición tipo BBCH se usa internamente para
ordenar, graficar y para la IA.

| Estado | Nombre | Control de helada |
|---|---|---|
| 1 | Yema apretada (*tight bud*) | no se controla (resiste -7 °C) |
| 2 | Yema blanca (*white bud*) | -2 °C |
| 3 | Repollo (*cabbage head*) | -2 °C |
| 4 | Apertura de yema (*bud break*) | -1 °C |
| 5 | Elongación (*bud elongation*) | 0 °C |
| 6 | Cuello rugoso (*roughneck*) | 0 °C |
| 7 | Gancho (*hook*) | 0 °C |
| 8 | Inicio floración (*early bloom*) | 1 °C |
| 9 | Inicio cuaja | 1 °C |
| 10 | Fruta verde | 0 °C |
| 11 | Fruta roja (*red fruit*, > 30 TAcy) | -1 °C |

El calendario esperado usado como prior (`phenology.EXPECTED_CALENDAR`) supone la Semana 1 en la
primera semana de septiembre (yema blanca) en el sur de Chile y puede ajustarse a cada localidad.

## 8. Arte

`tools/make_cran_art.py` dibuja el logo, la letra «FenoCran App», los cranberries de cada
variedad y los íconos a línea; luego `tools/make_ui_assets.py`, `tools/make_start_assets.py`,
`tools/make_splash_layers.py` y `tools/make_splash_lottie.py` generan el resto (íconos,
fondos, presplash y animación de apertura). Para usar arte propio, reemplace
`assets/logo_source.png` / `assets/wordmark_source.png` y vuelva a correr esos scripts.
