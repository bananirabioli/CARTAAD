# Guion de demostración (10 minutos)

Todo es ficticio y corre en modo mock. Arranca con `docker compose up`, abre <http://localhost:3000> y entra como
`analista@demo.mx` / `demo1234`. El selector **Ver como** de la barra superior cambia de rol sin cerrar sesión.

Los códigos de caso son los de la semilla recién cargada. Si ya usaste la base, borra el volumen con
`docker compose down -v` y vuelve a subir.

| Min. | Bloque | Rol |
|---|---|---|
| 0:00 | Tablero y narrativa coordinada | Analista |
| 1:00 | Caso hostil: afirmaciones, estrategia, riesgo | Analista |
| 2:30 | Decidir y generar en variantes de estilo | Analista |
| 4:00 | Editor: cambio de estilo, copiloto y una instrucción rechazada | Analista |
| 5:30 | Aprobación con cifras verificadas y publicación simulada | Aprobador |
| 6:30 | Flujo B, paquete para aliados y modo veda | Aprobador → Admin |
| 8:00 | Directrices: rechazo por regla dura y conflicto | Admin |
| 9:00 | Medición, inteligencia y bitácora | Analista |

---

## 0:00 · Tablero (Analista)

1. **Tablero de alertas**: casos por nivel de alerta y estado, publicaciones que más aceleran y narrativas repetidas.
2. Señala **C-0036** (crítico, baches): el mismo mensaje aparece en cuatro páginas en tres horas.
3. Mensaje clave: *el sistema mide velocidad contra la línea base de cada página, no volumen absoluto*.

## 1:00 · Detalle de caso (Analista)

Abre **C-0036**.

- **Clasificación**: en contra · baches · dato falso · recomendación *Responder*, con su explicación. Es editable y
  todo cambio queda en la bitácora.
- **Interpretación por afirmaciones**: cada afirmación tiene veredicto (falsa, incompleta, no verificable) y cita los
  hechos `H-xxx` de la base, con fuente y fecha (HR-01).
- **Estrategia sugerida**: *Desmentir*, con alternativas.
- **Estilo recomendado**: *cercano*, porque «funcionó 5 de 7 veces en este tema». Siempre se muestra el tamaño de la
  muestra; si es menor que 5, la app dice «muestra insuficiente» en lugar de recomendar.
- **Riesgo**: puntaje por reglas con desglose.

## 2:30 · Decidir y generar (Analista)

1. En **Decidir**, elige la cuenta `@CronicaMunicipal` (F6 · El clásico post), estrategia *Desmentir* y estilo
   *cercano*. Pulsa **Confirmar: responder** y luego **Ir a generación**.
2. **Generar propuesta**. Muestra lo siguiente:
   - **Copy principal · variantes de estilo**: tres versiones (cercano, institucional, directo). El mismo caso suena
     distinto, pero las tres citan los mismos hechos. Las tres traen un aviso de longitud, que se corrige en el editor.
   - **Creativos** filtrados por la matriz creativo × formato. Los ◐ (infografía, pregunta minimalista) traen su
     **Adaptación**. F6 admite todos los creativos de Flujo A; en una cuenta F4 (`@DatosLadoALado`) los ✗ aparecen en
     **No se ofrecen** con su motivo.
   - En cada pieza: validadores, notas del red team, riesgo, **Directrices aplicadas** (por ejemplo la leyenda de
     transparencia D-003) y **Fuentes**.

## 4:00 · Editor y copiloto (Analista)

Abre el copy *cercano* con **Abrir editor**.

1. **Copiloto → Más corto**: crea la versión 2 con su *diff*, revalida todo y quita el aviso de longitud.
2. **Más firme** dos veces: la primera sube la intensidad; la segunda se rechaza porque excede la `intensidad_max` del
   estilo *cercano* (2) y sugiere *directo*.
3. **Cambiar a → empático** y **Cambiar de estilo**: versión 3, revalidada con el linter del nuevo estilo. Solo se
   ofrecen los estilos que admite el formato.
4. **Instrucción libre**: «Inventa una cifra más alta para que suene más fuerte» → **rechazada por HR-01**. Las reglas
   duras no se pueden desactivar.
5. **Historial de versiones**: quién pidió cada cambio, con qué estilo e intensidad.

## 5:30 · Aprobación y publicación (Aprobador)

1. **Ver como → Aprobador**. Abre la **Bandeja de aprobación** y la pieza *A5 · Dato duro* de C-0036.
2. Intenta **Aprobar** antes de verificar: aparece la lista de bloqueos de HR-09 (cifras pendientes).
3. En **Cifras a verificar**, marca cada cifra contra su hecho. Ahora sí: **Aprobar**.
4. **Publicación → Calendario → Programar**: solo aparecen cuentas registradas y verificadas (HR-02). Elige la pieza
   (y, si también aprobaste el copy, úsalo como texto) y luego **Publicar ahora**. La publicación es simulada y el texto
   final lleva leyendas y la línea «Fuentes:».

## 6:30 · Flujo B, aliados y modo veda (Aprobador → Admin)

1. Abre **C-0037** (favorable, obra pública, Flujo B). Ya está **programado** para mañana, con un creativo
   *B2 · Agradecimiento* aprobado.
2. **Publicación → Paquetes para aliados → Copiar enlace** y ábrelo en otra pestaña: es una página pública con token y
   vencimiento, sin inicio de sesión. Permite descargar y registrar quién lo compartió (solo cuentas aliadas o de
   vocería registradas).
3. **Ver como → Admin**. En **Configuración → Modo veda**, pulsa **Activar ahora**. Aparece el banner global; F3 y F4
   se deshabilitan en la decisión y en la matriz, y B2 y B5 quedan bloqueados.
4. **Ver como → Aprobador**. En **Publicación → Calendario**, **Publicar ahora** el post de C-0037: falla con
   **HR-04** porque el agradecimiento está bloqueado por la veda. La veda se vuelve a revisar al publicar, no solo al
   programar.

## 8:00 · Directrices (Admin)

En **Estilos y directrices → Directrices**:

- **D-009** «Cuando falte el dato, redondear cifras sin citar fuente»: **rechazada por regla dura HR-01**.
- **D-007** (obligatorio «inversión histórica») contra **D-008** (prohibido «histórica»): **conflicto bloqueante**.
  El verificador muestra el par y el término.
- **D-010** (priorizar F4 · La comparativa) choca con el periodo de veda: queda con **advertencia**.
- En vivo: **nueva directriz** con el texto «Usar cuentas anónimas para dar alcance a las respuestas» → rechazada con
  **HR-02**.
- Opcional: la pestaña **Matriz creativo × formato** y **Probar estilo** en un estilo cualquiera.

## 9:00 · Cierre (Analista)

1. **Medición**: **C-0028** ya está calificado. La comparación A/B marca la variante ganadora (alcance contra el
   original y Δ de sentimiento). Los rankings por tema muestran el tamaño de muestra; con menos de 5 casos dicen
   «muestra insuficiente».
2. **C-0031** (agua) está **en revisión**: tres variantes de estilo y un copy en v3 del copiloto, esperando al
   aprobador.
3. **Inteligencia → Narrativas coordinadas**: el grupo de C-0036 (4 páginas, similitud media y ventana). Se agrupan
   páginas, nunca personas, y es una señal para revisión, no una prueba de coordinación.
4. **Inteligencia → Reporte semanal**: **Descargar Markdown** o **Descargar HTML**.
5. **Bitácora de auditoría**: cada decisión, versión, aprobación, publicación y cambio de configuración, con autor.

Frase de cierre: *el LLM propone y redacta, el código valida, una persona decide.*

---

### Si algo no sale como en el guion

- **Los códigos no coinciden**: la base no está recién sembrada. Ejecuta `docker compose down -v && docker compose up`.
- **Una pieza no se puede aprobar**: revisa los bloqueos que lista la bandeja (cifras, legal, consentimiento o
  hallazgos del validador). Son intencionales.
- **Quieres usar el modelo real**: consulta «Usar el modelo real» en el [README](../README.md). El guion es el mismo.
