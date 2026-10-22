# C-A-R-T-A-A-D

**Centro de Alerta y Respuesta Temprana a Amenazas Digitales**: prototipo beta con datos ficticios.

Monitorea páginas públicas, detecta publicaciones que aceleran, las clasifica e interpreta afirmación por afirmación
contra una base de hechos con fuente y fecha, sugiere estrategia y estilo, y genera copy y creativos en variantes de
estilo que pasan por validadores, red team y aprobación humana antes de una publicación **simulada**.

> **El LLM propone y redacta, el código valida, una persona decide.**

## Arranque rápido

```bash
docker compose up
```

- App: <http://localhost:3000> · API: <http://localhost:8000/docs>
- Funciona sin llaves externas: la IA corre en **modo mock** y las imágenes son *placeholders* con crédito.
- La primera vez construye las imágenes, migra la base (Postgres + pgvector) y carga la semilla. Tarda unos minutos.

Usuarios de demostración (contraseña `demo1234`). En modo demo, el selector **Ver como** de la barra superior cambia
de rol sin cerrar sesión.

| Correo | Rol |
|---|---|
| `analista@demo.mx` | Analista |
| `aprobador@demo.mx` | Aprobador |
| `legal@demo.mx` | Legal |
| `diseno@demo.mx` | Diseño |
| `admin@demo.mx` | Admin |
| `base@demo.mx` | Analista y dueña de la base de conocimiento |
| `candidatura@demo.mx` | Analista, solo del segundo cliente (demuestra el aislamiento) |

El guion de demostración de 10 minutos está en [`docs/DEMO.md`](docs/DEMO.md).

## Usar el modelo real

Copia `.env.example` a `.env` y define:

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=<id del modelo>   # obligatorio: el código no fija ningún modelo
```

Cada llamada queda registrada en **Configuración → Registro de IA** (paso, versión del prompt, estilo y directrices
aplicadas, latencia y resultado). Los prompts versionados están en `prompts/` y los esquemas de salida en `schemas/`.

## Desarrollo sin Docker

Requiere Python 3.12+, Node 22+ y pnpm.

```bash
make setup      # venv del backend, dependencias, Chromium de Playwright y node_modules
make dev-api    # FastAPI en :8000 con SQLite y la semilla automática
make dev-web    # Next.js en :3000
```

| Comando | Qué hace |
|---|---|
| `make test` | Pruebas del backend (reglas duras, validadores con casos adversariales, flujos A y B de punta a punta) |
| `make eval` | Set de evaluación → [`evals/report.md`](evals/report.md). `EVAL_PROVIDER=anthropic make eval` usa el modelo real |
| `make typecheck` / `make lint` | TypeScript y ESLint del frontend |
| `make openapi` | Regenera los tipos del frontend desde el OpenAPI de la API |
| `make migration m="..."` | Nueva migración de Alembic |
| `make seed-sources` | Agrega 100 fuentes ficticias para probar volumen |

## Arquitectura

| Pieza | Tecnología |
|---|---|
| Frontend | Next.js (App Router) · TypeScript · Tailwind · shadcn/ui · SWR; textos en `frontend/src/i18n/es-MX.json` |
| API | FastAPI · SQLAlchemy · Alembic · Pydantic |
| Datos | Postgres + pgvector (búsqueda semántica); SQLite en pruebas |
| Tareas | Celery + Redis: worker (render, generación) y beat (monitoreo, publicaciones programadas, recordatorios) |
| Render | Plantillas HTML → PNG con Playwright (Pillow como respaldo) |
| Archivos | Interfaz de almacenamiento: disco local o S3/MinIO (`docker compose --profile s3 up`) |
| IA | `MockProvider` y `AnthropicProvider` con el mismo contrato y esquemas; `ImageProvider` aparte |

```
backend/app/
  api/          rutas por módulo
  services/     dominio: casos, estilos y directrices, generación, publicación, medición, inteligencia
  guardrails/   hard_rules.py (HR-01 … HR-11)
  validators/   cifras, afirmaciones, compatibilidad, etiquetas y linter de estilo
  ai/           proveedores, pasos y fixtures del mock
  render/       plantillas por formato y creativo
  seed/         datos ficticios
frontend/src/   pantallas, componentes e i18n
prompts/ schemas/ fixtures/ evals/ docs/
```

Más detalle en [`docs/PLAN.md`](docs/PLAN.md) y las desviaciones del plan en [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Reglas duras

Viven en `backend/app/guardrails/hard_rules.py`, cada una con pruebas. Ninguna configuración, estilo ni directriz puede
desactivarlas; una directriz que las contradice se rechaza con el id de la regla.

| Id | Regla |
|---|---|
| HR-01 | Todo dato muestra fuente y fecha |
| HR-02 | Solo cuentas reales registradas |
| HR-03 | No se perfila a quien comenta |
| HR-04 | Modo veda y restricciones |
| HR-05 | Las quejas legítimas se canalizan |
| HR-06 | Una imagen generada no es evidencia |
| HR-07 | Testimonios reales y figuras representativas |
| HR-08 | Afirmaciones sobre actores con respaldo |
| HR-09 | Aprobación humana y cifras verificadas |
| HR-10 | Sin imitar a terceros; sátira con revisión legal |
| HR-11 | Las imágenes generadas no llevan texto ni cifras |

## Alcance

- Todos los datos son **ficticios**: Municipio Ejemplo, Gobierno Estatal Ejemplo, Partido Azul y demás. No hay personas,
  partidos, medios ni marcas reales.
- La publicación es **simulada**: nada sale a redes reales.
- Fuera de alcance: *scraping* de redes, cuentas falsas o bots, perfilado de ciudadanos y facturación. Las narrativas
  coordinadas agrupan páginas públicas, nunca personas.
