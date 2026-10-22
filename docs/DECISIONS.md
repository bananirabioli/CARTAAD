# Decisiones técnicas

Registro de desviaciones o precisiones respecto al stack propuesto. Cada entrada: contexto, decisión y por qué.

## D-01 · Pruebas sobre SQLite; producción sobre PostgreSQL + pgvector

- **Contexto:** el stack pide PostgreSQL + pgvector. Las pruebas deben correr rápido y sin Docker.
- **Decisión:** los modelos usan tipos portables (`JSON` con variante `JSONB`, `UTCDateTime`, `Vector`). `Vector` es
  pgvector en PostgreSQL y una lista JSON en SQLite; la búsqueda semántica usa el operador `<=>` en PostgreSQL y
  similitud coseno en Python en SQLite. `docker compose up` usa siempre PostgreSQL + pgvector.
- **Por qué:** `make test` corre en segundos sin servicios externos y el código de dominio no depende del motor.

## D-02 · Embeddings locales por hashing (sin descargas)

- **Contexto:** "por defecto un modelo local ligero, sin llaves".
- **Decisión:** `HashingEmbeddingProvider` (n-gramas de palabras y caracteres con *feature hashing*, 256 dims,
  normalizado L2). Interfaz `EmbeddingProvider` lista para un modelo real (p. ej. `fastembed`).
- **Por qué:** cero descargas ni GPU, determinista para pruebas; suficiente para agrupar narrativas parecidas en la demo.

## D-03 · `MockProvider` compositivo

- **Contexto:** el modo mock debe sostener la demo completa, incluidas capturas manuales nuevas.
- **Decisión:** el mock no devuelve respuestas fijas por caso: combina reglas deterministas (palabras clave
  configurables por tema) con plantillas por estilo en `fixtures/mock/styles/*.json`. Usa solo los hechos del contexto
  que recibe y cita sus `fact_id`, igual que se exige al modelo real.
- **Por qué:** cualquier publicación nueva produce una salida coherente, distinta por estilo y estable para las pruebas.

## D-04 · "Pieza" unifica variantes de copy y creativos

- **Decisión:** `Piece` con `kind = copy | creative`. Ambas comparten validadores, `PieceVersion`, verificación por
  cifra, revisión legal, aprobación, programación y métricas (`variant_id` = id de pieza).
- **Por qué:** un solo flujo de revisión y un solo punto de control para HR-09.

## D-05 · Estilos y directrices versionados por fila

- **Decisión:** cada versión es una fila (`slug`/`code` + `version`). Editar una versión activa crea un borrador
  `version + 1`; activar archiva la anterior. `Proposal`/`Piece`/`AiRun` guardan `style_id` + `style_version` y la lista
  de directrices aplicadas con su versión.
- **Por qué:** trazabilidad exacta de qué reglas editoriales produjeron cada pieza.

## D-06 · Plantillas base clonadas por cliente

- **Decisión:** los catálogos base (`client_id = NULL`: temas, etiquetas, estilos, creativos, formatos, matriz) se
  clonan al crear un cliente; cada cliente edita su copia. Las plantillas base son de solo lectura y se pueden volver
  a clonar.
- **Por qué:** aislamiento estricto entre clientes sin lógica de herencia en cada consulta.

## D-07 · Proxy de Next.js para la API

- **Decisión:** el navegador solo habla con Next.js; un *route handler* (`/api/[...path]`) reenvía a FastAPI leyendo
  `API_INTERNAL_URL` en tiempo de ejecución.
- **Por qué:** cookies de sesión en el mismo origen (sin CORS) y la misma imagen sirve en local y en Docker.

## D-08 · i18n propio y ligero

- **Decisión:** `frontend/src/i18n/es-MX.json` + función `t()`; el backend tiene `backend/app/i18n/es_MX.json` para los
  mensajes que genera (validadores, reglas duras, errores).
- **Por qué:** un solo idioma de interfaz por ahora; evita el ruteo por *locale* de librerías más pesadas y deja todas
  las cadenas fuera del código.

## D-09 · Celery en modo *eager* fuera de Docker

- **Decisión:** `CELERY_EAGER=true` (por defecto local y en pruebas) ejecuta las tareas en línea. En Docker hay
  worker + beat reales sobre Redis.
- **Por qué:** pruebas E2E deterministas sin Redis.

## D-10 · Renderizador de respaldo con Pillow

- **Decisión:** el render oficial es HTML/CSS → PNG con Playwright (Chromium) en el worker. Fuera de Docker y en
  pruebas se usa `RENDERER=pillow`, que produce un PNG legible a partir de los mismos slots.
- **Por qué:** no exigir Chromium para `make test`; las plantillas HTML se prueban por separado.

## D-11 · Next.js 16, Tailwind 4 y shadcn/ui (Radix)

- **Decisión:** versiones actuales al iniciar el proyecto (Next 16.4, React 19.3, Tailwind 4.3, shadcn CLI 4 con base
  Radix). Se desactivó `cacheComponents`: la app es un panel con datos por sesión y cliente, sin contenido estático.
  Tipografía con pila del sistema (sin descarga de fuentes en el build).
- **Por qué:** menos piezas móviles en una beta; los tokens viven en `frontend/src/styles/tokens.css`.

## D-12 · Contraseñas con PBKDF2 de la biblioteca estándar

- **Decisión:** `hashlib.pbkdf2_hmac` (SHA-256) con sal; sesión firmada con `itsdangerous` en cookie `httponly`.
- **Por qué:** auth simple sin dependencias extra, adecuada para usuarios semilla de una beta.

## D-13 · `AnthropicProvider` con salidas estructuradas nativas

- **Decisión:** `client.messages.parse(output_format=<modelo Pydantic>)` por paso; la imagen de la captura va como bloque
  base64. El modelo sale de `LLM_MODEL` (sin valor por defecto en código). `stop_reason == "refusal"` se registra en
  `AiRun` como `refused` y se muestra al usuario; no hay *fallback* automático a otro modelo porque el modelo es
  configurable por entorno (se puede agregar cuando se fije uno).
- **Por qué:** validación garantizada contra el mismo esquema que usa el `MockProvider`; un reintento con el error de
  validación como retroalimentación si aun así no cumple.

## D-14 · Alcance estricto y severidad de directrices sugeridas

- **Decisión:** una directriz con alcance (temas, formatos, cuentas, estilos, flujos) solo aplica cuando el contexto de
  generación trae un valor que coincide; sin valor no aplica. El vocabulario prohibido por una directriz *sugerida*
  produce aviso (no bloqueo) en el linter; el del estilo, las líneas rojas y las obligatorias bloquean.
- **Por qué:** "Probar estilo" no conoce el formato y no debe arrastrar leyendas de un formato concreto; "sugerida"
  conserva su significado.

## D-15 · El modo veda existe desde M2

- **Decisión:** el modelo `RestrictionMode` se adelantó a M2 porque el verificador de directrices debe detectar choques
  con vedas vigentes o programadas. La gestión en pantalla llega en M6.

## D-16 · Métricas manuales o simuladas, una fila de historial por variante

- **Decisión:** las métricas se capturan a mano o se simulan de forma determinista (semilla = caso + pieza) porque no hay
  conexión a redes reales. El alcance del original se estima como interacciones × 9 cuando no se captura. Al calificar
  un caso se escribe una fila de `ResponseHistory` **por variante medida** (formato, estilo, estrategia, creativo,
  alcance relativo y Δ de sentimiento), que alimenta el contexto de aprendizaje y los rankings.
- **Por qué:** el A/B compara variantes; una sola fila por caso perdería qué variante funcionó. La simulación permite la
  demo sin tocar redes y queda marcada como `simulado` en pantalla.

## D-17 · Evals de regresión sobre el pipeline real

- **Decisión:** `make eval` corre 20 casos (clasificación, *grounding*, copy por estilo, directrices contra reglas duras)
  sobre una base SQLite temporal recién sembrada, usando los mismos servicios que la API. Con el MockProvider es una
  prueba de regresión (sale con código 1 si algún caso falla); con `EVAL_PROVIDER=anthropic` mide calidad del modelo real
  y siempre escribe el reporte.
- **Por qué:** evaluar el pipeline completo (reglas, validadores, linter) y no solo el texto del modelo.

## D-18 · Palabras clave débiles en temas

- **Decisión:** una palabra clave de tema con prefijo `~` cuenta medio punto (p. ej. `~calle` en baches), para que una
  mención incidental no gane sobre la palabra clave fuerte de otro tema ("calle de la escuela" + "luminarias" →
  seguridad).

## D-19 · Narrativas coordinadas por página y como señal

- **Decisión:** se agrupan publicaciones no históricas de páginas distintas, del mismo tema y dentro de la ventana
  configurada, por similitud de *embeddings* (componentes conexas sobre `repeated_similarity`). Un grupo es «patrón
  coordinado» con 3 o más páginas, similitud media ≥ `coordinated_similarity` y lapso dentro de la ventana; si no, es
  «mensaje repetido». La interfaz y el reporte aclaran que es una señal para revisión, no una prueba.
- **Por qué:** el alcance excluye perfilar ciudadanos (HR-03); la unidad es la página pública monitoreada.

## D-20 · Casos avanzados de la semilla por el pipeline real

- **Decisión:** los tres casos avanzados (calificado, en revisión con versiones del copiloto, programado con paquete
  para aliados) se construyen llamando a los mismos servicios que la API, en lugar de insertar filas. En la API, la
  semilla automática corre en un hilo (`asyncio.to_thread`) para que el render con Playwright síncrono funcione.
- **Por qué:** así la semilla respeta reglas duras, validadores, versiones y bitácora, y no puede quedar en un estado
  que el sistema no permitiría.
