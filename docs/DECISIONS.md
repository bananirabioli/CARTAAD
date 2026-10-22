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
