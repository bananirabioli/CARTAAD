"""Base templates (client_id = NULL): tag taxonomy, styles, formats, creatives and the creative × format matrix.

All of this is editable data. Nothing here is hard-wired into the engine.
"""

TAG_DIMENSIONS = [
    ("tono", "Tono", "categorical", ["institucional", "conversacional", "firme", "explicativo", "sobrio", "factual", "satirico", "empatico", "calido", "coloquial", "neutral"]),
    ("registro", "Registro", "categorical", ["formal", "cotidiano", "coloquial"]),
    ("intencion", "Intención", "categorical", ["informar", "desmentir", "contextualizar", "reencuadrar", "contrastar", "agradecer", "desescalar", "movilizar"]),
    ("humor", "Humor", "categorical", ["ninguno", "ligero", "satirico"]),
    ("audiencia", "Audiencia", "categorical", ["ciudadania_general", "base_propia", "aliados", "medios"]),
    ("riesgo", "Riesgo", "categorical", ["bajo", "medio", "alto"]),
    ("intensidad", "Intensidad", "numeric", ["1", "2", "3", "4", "5"]),
]

TAG_LABELS = {
    "satirico": "satírico",
    "empatico": "empático",
    "calido": "cálido",
    "ciudadania_general": "ciudadanía general",
    "base_propia": "base propia",
    "explicativo": "explicativo",
}

F1, F2, F3, F4, F5, F6 = "formato_contexto", "formato_historieta", "formato_titeres", "formato_comparativa", "formato_voz_pueblo", "formato_clasico"


def _style(slug, name, description, tags, imin, imax, haz, evita, prohibited, length, risk, formats, palette, visual, good, bad, **extra):  # noqa: ANN001, ANN003
    return {
        "slug": slug,
        "name": name,
        "description": description,
        "tags": tags,
        "intensity_min": imin,
        "intensity_max": imax,
        "voice": extra.pop("voice", {"persona": "nosotros_institucional", "trato": "usted", "idioma": "es-MX"}),
        "guidelines": {"haz": haz, "evita": evita},
        "preferred_vocab": extra.pop("preferred", []),
        "prohibited_vocab": prohibited,
        "length": {"copy_principal": {"min": length[0], "max": length[1], "unidad": "caracteres"}},
        "emoji_usage": extra.pop("emoji", "ninguno"),
        "caps_usage": extra.pop("caps", "normal"),
        "good_examples": good,
        "bad_examples": bad,
        "visual_guide": visual,
        "palette": palette,
        "allowed_formats": formats,
        "risk": risk,
        "requires_legal": extra.pop("requires_legal", risk == "alto"),
        **extra,
    }


STYLES = [
    _style(
        "institucional", "Institucional", "Voz oficial, precisa y con fuente en cada dato.",
        {"tono": ["institucional"], "registro": ["formal"], "intencion": ["informar"], "humor": ["ninguno"], "audiencia": ["ciudadania_general", "medios"]},
        1, 2,
        ["Tercera persona o «nosotros» institucional", "Cada dato con su fuente y fecha", "Frases completas y precisas"],
        ["Adjetivos calificativos", "Ironía", "Jerga o coloquialismos"],
        ["mentiroso", "corrupto", "ridículo", "vergüenza"], (160, 420), "bajo", [F1, F2, F4, F6],
        ["#1F3A5F", "#E8EDF3", "#5B7A99", "#F2B134"],
        "Composición ordenada en retícula, mucho espacio en blanco, azul pizarra y gris; íconos lineales; la cifra en un bloque destacado con su fuente al pie.",
        ["El Municipio Ejemplo informa que, de acuerdo con su informe semestral, se atendieron los reportes de la Colonia Centro."],
        ["¡Otra mentira de la oposición!"],
        preferred=["informa", "de acuerdo con", "con base en"],
    ),
    _style(
        "cercano", "Cercano", "Conversacional y cotidiano: explica sin tecnicismos y baja la tensión.",
        {"tono": ["conversacional"], "registro": ["cotidiano"], "intencion": ["informar", "desescalar"], "humor": ["ninguno"], "audiencia": ["ciudadania_general"]},
        1, 2,
        ["Frases cortas, una idea por frase", "Un ejemplo cotidiano cuando ayude a entender", "Empezar por lo que le importa a la persona"],
        ["Tecnicismos sin explicar", "Diminutivos paternalistas", "Ironía o sarcasmo"],
        ["mentiroso", "corrupto"], (120, 280), "bajo", [F1, F2, F3, F5, F6],
        ["#2F6B4F", "#F4EDE1", "#D98C4A", "#3B3B3B"],
        "Ilustración cálida de trazo suave, colores tierra y verde, escenas de barrio sin rostros identificables; textos grandes y legibles.",
        ["Sabemos que un bache en su calle complica el día. Le contamos qué se está haciendo y cómo reportarlo."],
        ["Estimado ciudadano, conforme a la normatividad aplicable se informa lo siguiente."],
    ),
    _style(
        "directo", "Directo", "Firme: la corrección va primero, con dato y fuente enseguida.",
        {"tono": ["firme"], "registro": ["formal"], "intencion": ["desmentir"], "humor": ["ninguno"], "audiencia": ["ciudadania_general", "medios"]},
        1, 3,
        ["La corrección va en la primera línea", "Una idea por frase", "Dato y fuente inmediatamente después"],
        ["Adjetivar al adversario", "Mayúsculas sostenidas", "Ataques personales"],
        ["mentiroso", "corrupto", "ignorante", "basura"], (80, 240), "medio", [F1, F4, F6],
        ["#111827", "#FFFFFF", "#C0392B", "#F5F5F5"],
        "Alto contraste: fondo claro u oscuro y un solo color de acento para la palabra clave de la corrección; titular en tipografía condensada.",
        ["Dato incorrecto. Entre enero y junio se repararon los baches reportados; aquí la fuente."],
        ["¡¡FALSO!! Los de siempre mintiendo otra vez."],
        caps="solo_rotulos",
    ),
    _style(
        "didactico", "Didáctico", "Explica la mecánica del tema paso a paso, con analogías.",
        {"tono": ["explicativo"], "registro": ["cotidiano"], "intencion": ["informar"], "humor": ["ninguno"], "audiencia": ["ciudadania_general"]},
        1, 2,
        ["Analogías simples", "Pasos en orden, un concepto por lámina o viñeta", "Cerrar con qué puede hacer la persona"],
        ["Saturar de cifras", "Tecnicismos sin explicar"],
        ["obviamente", "como todos saben"], (150, 400), "bajo", [F2],
        ["#2D4B8E", "#FFF7E6", "#F28C28", "#7FB069"],
        "Viñetas de historieta con figuras geométricas amables (círculos y bloques), flechas y globos de diálogo; colores primarios suavizados; sin parecido con personajes conocidos.",
        ["Piénselo como una casa con tres dueños: cada nivel de gobierno cuida una parte de la calle."],
        ["Como todos saben, la competencia concurrente se rige por el artículo correspondiente."],
    ),
    _style(
        "alerta_contexto", "Alerta de contexto", "Sobrio y seco: señala qué le falta a la publicación y aporta el dato.",
        {"tono": ["sobrio"], "registro": ["formal"], "intencion": ["contextualizar"], "humor": ["ninguno"], "audiencia": ["ciudadania_general"]},
        1, 3,
        ["Señalar qué le falta a la publicación original", "Aportar el dato con fuente", "Usar «falso» solo si el veredicto de la afirmación es falsa"],
        ["Adjetivos", "Exclamaciones", "Atribuir intenciones"],
        ["mentiroso", "manipulador", "corrupto"], (100, 260), "medio", [F1],
        ["#1A1A1A", "#FFD400", "#FFFFFF", "#6B6B6B"],
        "Captura original al fondo con velo oscuro; rótulo tipo alerta en amarillo y negro con la palabra CONTEXTO; texto breve en bloque blanco.",
        ["A esta publicación le falta contexto: la avenida que muestra es de jurisdicción estatal."],
        ["¡Manipulan la información!"],
        caps="solo_rotulos",
    ),
    _style(
        "contrastivo", "Contrastivo", "Factual: compara lo equivalente, con la misma base y el mismo periodo.",
        {"tono": ["factual"], "registro": ["formal"], "intencion": ["contrastar"], "humor": ["ninguno"], "audiencia": ["ciudadania_general", "medios"]},
        1, 3,
        ["Mismo periodo y misma base en ambos lados", "Comparar solo lo equivalente y verificable", "Cerrar con la frase de cierre configurada"],
        ["Comparar cosas sin equivalencia verificable", "Adjetivos sobre el otro lado"],
        ["mentiroso", "corrupto", "flojos"], (120, 300), "medio", [F4],
        ["#243B53", "#F0F4F8", "#2CB1BC", "#D64545"],
        "Dos paneles simétricos con fotos reales de archivo y crédito visible; línea divisoria vertical; misma escala tipográfica en ambos lados.",
        ["Mismo año, misma base: inversión municipal y estatal en obra pública, lado a lado."],
        ["Nosotros sí trabajamos, ellos no."],
    ),
    _style(
        "satirico", "Satírico", "Ironía sobre hechos verificables con figuras que representan roles o instituciones.",
        {"tono": ["satirico"], "registro": ["coloquial"], "intencion": ["reencuadrar"], "humor": ["satirico"], "audiencia": ["base_propia", "ciudadania_general"]},
        1, 4,
        ["Ironía sobre hechos verificables", "Figuras que representan roles o instituciones", "Exagerar la situación, nunca a la persona"],
        ["Personas reales identificables", "Rasgos físicos", "Discriminación", "Humor sobre víctimas o tragedias", "Afirmaciones sin respaldo"],
        ["feo", "gordo", "enano", "loco", "ridículo"], (80, 240), "alto", [F3],
        ["#6A4C93", "#FFCA3A", "#8AC926", "#1982C4", "#FF595E"],
        "Figuras tipo títere de diseño propio: cuerpos de fieltro geométricos, ojos de botón, cada figura con un letrero que nombra el rol o la institución (el Municipio, el Gobierno Estatal); escenario de teatrino sencillo; sin parecido con personajes de terceros ni con personas reales.",
        ["—¿Y la avenida? —preguntó el Municipio. —Es mía —contestó el letrero del Gobierno Estatal."],
        ["Miren la cara del funcionario, ¡parece un sapo!"],
    ),
    _style(
        "voz_ciudadana_representativa", "Voz ciudadana representativa", "Figuras ilustradas de sectores de la población que responden al argumento.",
        {"tono": ["coloquial", "empatico"], "registro": ["cotidiano"], "intencion": ["contextualizar", "desescalar"], "humor": ["ligero"], "audiencia": ["ciudadania_general"]},
        1, 2,
        ["Siempre con la etiqueta «ilustración representativa»", "Hablar desde la experiencia cotidiana de un sector, sin datos personales"],
        ["Presentarse como persona real", "Inventar testimonios con nombre o cifra", "Estereotipos"],
        ["mentiroso", "corrupto"], (100, 260), "medio", [F5],
        ["#E07A5F", "#F4F1DE", "#3D405B", "#81B29A"],
        "Figuras ilustradas planas que representan sectores (comercio, estudiantes, personas mayores) sin rasgos de personas reales; etiqueta visible «ilustración representativa».",
        ["Como quien abre su negocio temprano, lo que importa es saber cuándo queda lista la calle."],
        ["Soy doña Marta, vecina de la Colonia Centro, y les digo que todo es mentira."],
    ),
    _style(
        "periodistico", "Periodístico", "Neutral e informativo: titular, bajada y fuente atribuida.",
        {"tono": ["neutral"], "registro": ["formal"], "intencion": ["informar"], "humor": ["ninguno"], "audiencia": ["ciudadania_general", "medios"]},
        1, 2,
        ["Titular y bajada", "Atribuir la fuente en el cuerpo", "Pirámide invertida"],
        ["Imitar el lenguaje o la marca de un medio real", "Opinión en el titular"],
        ["exclusiva", "última hora"], (200, 500), "bajo", [F6],
        ["#222222", "#FAFAFA", "#B22222", "#E5E5E5"],
        "Nota estilo revista digital de identidad propia: titular serif grande, bajada, foto real con crédito y cintillo de sección; nunca imitar la marca de un medio real.",
        ["Avanza la repavimentación en la Avenida Central. La obra corresponde al programa estatal, según el documento oficial."],
        ["ÚLTIMA HORA: escándalo en la avenida."],
    ),
    _style(
        "empatico", "Empático", "Reconoce el problema antes de informar; solo promete lo respaldado.",
        {"tono": ["empatico"], "registro": ["cotidiano"], "intencion": ["desescalar", "informar"], "humor": ["ninguno"], "audiencia": ["ciudadania_general"]},
        1, 1,
        ["Reconocer el problema antes de dar información", "Prometer solo lo respaldado por un hecho o compromiso de la base", "Decir cómo se canaliza el caso"],
        ["Minimizar", "El «pero» después de reconocer", "Culpar a la persona"],
        ["pero", "exageran", "no es para tanto"], (120, 300), "bajo", [F5, F6],
        ["#5B8E7D", "#F7F3E9", "#BC4B51", "#8CB369"],
        "Fotografía o ilustración de servicio (cuadrillas trabajando), tonos cálidos y suaves; mensaje centrado en la persona.",
        ["Tiene razón en que la fuga afecta su día a día. Ya canalizamos su reporte y le daremos seguimiento."],
        ["Entendemos, pero la verdad es que exageran."],
    ),
    _style(
        "reconocimiento", "Reconocimiento", "Cálido: reconoce a quien publicó o participó sin apropiarse del mérito.",
        {"tono": ["calido"], "registro": ["cotidiano"], "intencion": ["agradecer"], "humor": ["ligero"], "audiencia": ["ciudadania_general", "aliados"]},
        1, 1,
        ["Reconocer a quien publicó o participó", "Dar crédito al esfuerzo ciudadano"],
        ["Triunfalismo", "Apropiarse del mérito ciudadano"],
        ["gracias a nosotros", "histórico"], (80, 220), "bajo", [F2, F6],
        ["#F4A259", "#FDF6EC", "#5B8E7D", "#BC4B51"],
        "Fotografía real con crédito o ilustración luminosa; marco simple, tipografía redondeada.",
        ["Gracias por compartir cómo quedó su parque: el cuidado de los vecinos lo hace posible."],
        ["Gracias a nosotros su colonia ya es otra."],
    ),
]

FORMATS = [
    {"slug": F1, "code": "F1", "name": "Contexto", "template": "contexto", "default_style_slug": "alerta_contexto",
     "allowed_style_slugs": ["institucional", "directo", "cercano"],
     "description": "La captura sube como base del diseño con un rótulo tipo ALERTA y la palabra CONTEXTO; el contexto se explica en el copy. En Flujo B el rótulo es neutro.",
     "options": {"alert_label": "ALERTA", "label_flow_a": "CONTEXTO", "label_flow_b": "DATO", "uses_capture": True}},
    {"slug": F2, "code": "F2", "name": "Infografía tipo historieta", "template": "historieta", "default_style_slug": "didactico",
     "allowed_style_slugs": ["cercano", "institucional", "reconocimiento"],
     "description": "Viñetas que responden a la postura, explican la mecánica del tema y contrastan lo hecho por cada parte.",
     "options": {"panels": 4}},
    {"slug": F3, "code": "F3", "name": "Show de títeres", "template": "titeres", "default_style_slug": "satirico",
     "allowed_style_slugs": ["satirico", "cercano"],
     "description": "Figuras tipo títere de diseño propio, una por rol o institución, que recrean el conflicto en tono satírico. Nunca caricaturas de personas reales.",
     "options": {"satirical": True, "figures_represent": "roles e instituciones"}},
    {"slug": F4, "code": "F4", "name": "La comparativa", "template": "comparativa", "default_style_slug": "contrastivo",
     "allowed_style_slugs": ["institucional", "directo"],
     "description": "Dos paneles con fotos reales de archivo (con crédito) y un contraste equivalente de la base; frase de cierre configurable.",
     "options": {"closing_phrase": "Mismo periodo, misma base: compare usted.", "requires_real_photos": True}},
    {"slug": F5, "code": "F5", "name": "La voz del pueblo", "template": "voz_pueblo", "default_style_slug": "voz_ciudadana_representativa",
     "allowed_style_slugs": ["cercano", "empatico"],
     "description": "Figuras ilustradas que representan sectores de la población y responden al argumento; siempre con la etiqueta «ilustración representativa».",
     "options": {"representative_label": "ilustración representativa", "illustrated_figures": True}},
    {"slug": F6, "code": "F6", "name": "El clásico post", "template": "clasico", "default_style_slug": "periodistico",
     "allowed_style_slugs": ["institucional", "cercano", "directo", "empatico", "reconocimiento"],
     "description": "Nota en imagen estilo revista digital con fotos reales del banco; identidad propia, sin imitar a un medio real.",
     "options": {"masthead": "Crónica Municipal"}},
]

# slug, code, flow, name, description, slots, template, requires_fact, requires_consent, requires_real_photo, text_only, is_comparison
CREATIVES = [
    ("contexto_responsabilidad", "A1", "A", "Contexto (responsabilidad compartida)", "Explica la responsabilidad compartida, cómo se distribuye el presupuesto y qué porcentaje ha invertido cada nivel de gobierno.", ["titulo", "cuerpo", "puntos"], "responsabilidad", True, False, False, False, False),
    ("infografia", "A2", "A", "Infografía", "El punto de vista explicado con ilustraciones e íconos.", ["titulo", "puntos"], "infografia", False, False, False, False, False),
    ("pregunta_minimalista", "A3", "A", "Pregunta minimalista", "Solo el título y una pregunta que lo cuestiona.", ["titulo", "pregunta"], "pregunta", False, False, False, False, False),
    ("mito_vs_realidad", "A4", "A", "Mito vs realidad", "La afirmación contra el dato verificado.", ["mito", "realidad"], "mito_realidad", True, False, False, False, False),
    ("dato_duro", "A5", "A", "Dato duro", "Una sola cifra grande con su fuente.", ["cifra", "descripcion"], "dato_duro", True, False, False, False, False),
    ("antes_despues", "A6", "A", "Antes y después", "Fotos de la obra o acción realizada, del banco de imágenes.", ["titulo", "pie"], "antes_despues", False, False, True, False, True),
    ("linea_tiempo", "A7", "A", "Línea del tiempo", "Qué se ha hecho sobre el tema y cuándo.", ["titulo", "hitos"], "linea_tiempo", True, False, False, False, False),
    ("carrusel_explicativo", "A8", "A", "Carrusel explicativo", "De 5 a 7 láminas que desarman la narrativa paso a paso.", ["laminas"], "carrusel", False, False, False, False, False),
    ("guion_video", "A9", "A", "Guion de video corto", "Un vocero explica en 30 segundos (salida de texto).", ["escenas"], "guion", False, False, False, True, False),
    ("voz_ciudadana", "A10", "A", "Voz ciudadana (testimonio real)", "Testimonio real de un beneficiario; requiere consentimiento adjunto.", ["cita", "persona"], "testimonio", False, True, True, False, False),
    ("repost_contexto", "B1", "B", "Repost con contexto", "Compartir la publicación agregando un dato que la refuerce.", ["comentario", "dato"], "repost", True, False, False, False, False),
    ("agradecimiento", "B2", "B", "Agradecimiento o reconocimiento", "A quien publicó o al ciudadano involucrado.", ["mensaje"], "agradecimiento", False, False, False, False, False),
    ("lo_que_no_se_vio", "B3", "B", "Lo que no se vio", "La historia detrás de la acción que se elogia.", ["titulo", "historia"], "historia", False, False, False, False, False),
    ("guion_dueto", "B4", "B", "Guion de dueto o stitch", "Reacción en video a la publicación original (salida de texto).", ["escenas"], "guion", False, False, False, True, False),
    ("carrusel_resultados", "B5", "B", "Carrusel de resultados", "Conecta la acción con otras similares.", ["laminas"], "carrusel", True, False, False, False, False),
    ("pieza_aliados", "B6", "B", "Pieza para aliados", "Versión lista para que la compartan vocerías y aliados.", ["titulo", "mensaje", "copy_sugerido"], "aliados", False, False, False, False, False),
]

_FMTS = [F1, F2, F3, F4, F5, F6]
# ✓ = full, ◐ = partial (note = adaptation), ✗ = none (note = reason)
_MATRIX_ROWS = {
    "contexto_responsabilidad": ["✓", "✓", ("◐", "Las figuras explican el reparto en escena; las cifras van en el rótulo, nunca en boca de una figura."), ("✗", "La comparativa exige dos lados equivalentes; la responsabilidad compartida no es una comparación."), ("◐", "Las figuras representativas preguntan y el rótulo responde con el dato."), "✓"],
    "infografia": [("◐", "La infografía se reduce a tres íconos sobre la captura."), "✓", ("✗", "El show de títeres no admite infografía."), ("✗", "Formato de dos paneles sin espacio para infografía."), ("✗", "Las figuras representativas no se mezclan con infografía."), ("◐", "Se integra como recuadro dentro de la nota.")],
    "pregunta_minimalista": ["✓", ("✗", "La historieta necesita secuencia, no una sola pregunta."), ("✗", "Una pregunta aislada en sátira se presta a malinterpretación."), ("✗", "La comparativa requiere dos lados con datos."), "✓", ("◐", "La pregunta se usa como titular de la nota.")],
    "mito_vs_realidad": ["✓", ("◐", "Mito y realidad en dos viñetas consecutivas."), ("◐", "Una figura dice el mito y el rótulo muestra la realidad con su fuente."), ("◐", "Panel izquierdo: mito; derecho: realidad, con el mismo periodo y base."), "✓", "✓"],
    "dato_duro": ["✓", ("◐", "La cifra va en un cartel dentro de la viñeta."), ("✗", "Una cifra aislada en sátira se saca de contexto."), ("◐", "La cifra se muestra en ambos paneles con la misma base."), ("◐", "La cifra aparece en el rótulo, no en boca de la figura."), "✓"],
    "antes_despues": [("◐", "Antes y después en miniatura sobre la captura."), ("✗", "Las fotos reales no se mezclan con viñetas ilustradas."), ("✗", "Las fotos reales no se mezclan con títeres ilustrados."), "✓", ("✗", "Las fotos reales no se mezclan con figuras representativas."), "✓"],
    "linea_tiempo": [("◐", "Línea del tiempo de tres hitos como máximo."), "✓", ("✗", "No aplica al show de títeres."), ("✗", "No es una comparación de dos lados."), ("✗", "No aplica a figuras representativas."), "✓"],
    "carrusel_explicativo": ["✓", "✓", "✓", ("◐", "Cada lámina mantiene los dos paneles con la misma base."), "✓", "✓"],
    "guion_video": ["✓", "✓", "✓", "✓", "✓", "✓"],
    "voz_ciudadana": [("◐", "El testimonio real se muestra como cita textual con su consentimiento."), ("✗", "Un testimonio real no se ilustra como historieta (HR-06, HR-07)."), ("✗", "Un testimonio real no se mezcla con títeres (HR-06, HR-07)."), ("✗", "La comparativa no lleva testimonios."), ("✗", "No se mezcla un testimonio real con figuras representativas (HR-07)."), "✓"],
    "repost_contexto": [("◐", "El rótulo ALERTA se reemplaza por un rótulo neutro."), ("✗", "El repost no se adapta a viñetas."), ("✗", "El repost no se adapta al show de títeres."), ("◐", "La publicación original y el dato van en paneles separados."), ("✗", "No aplica a figuras representativas."), ("◐", "Se cita la publicación dentro de la nota.")],
    "agradecimiento": [("✗", "El formato Contexto no es para agradecer."), ("✗", "La historieta no se usa para agradecer."), ("◐", "Las figuras agradecen en nombre de la institución, sin personas reales."), ("✗", "No es una comparación."), ("◐", "Las figuras representativas agradecen; etiqueta visible."), "✓"],
    "lo_que_no_se_vio": [("◐", "La historia va en el copy; la imagen es la captura con rótulo neutro."), "✓", ("◐", "La historia detrás se cuenta con títeres de roles."), ("◐", "Antes y después de la acción en dos paneles."), ("◐", "Una figura representativa cuenta la historia; etiqueta visible."), "✓"],
    "guion_dueto": ["✓", "✓", "✓", "✓", "✓", "✓"],
    "carrusel_resultados": [("◐", "Carrusel de tres láminas con rótulo neutro."), "✓", ("✗", "La sátira no se usa para presentar resultados."), "✓", ("◐", "Las figuras presentan cada resultado; etiqueta visible."), "✓"],
    "pieza_aliados": [("✗", "El formato Contexto es de respuesta, no para aliados."), "✓", ("✗", "La sátira no se distribuye a aliados."), "✓", "✓", "✓"],
}
_LEVEL = {"✓": "full", "◐": "partial", "✗": "none"}


def matrix_rows() -> list[tuple[str, str, str, str]]:
    rows = []
    for creative, cells in _MATRIX_ROWS.items():
        for fmt, cell in zip(_FMTS, cells, strict=True):
            mark, note = (cell, "") if isinstance(cell, str) else cell
            rows.append((creative, fmt, _LEVEL[mark], note))
    return rows
