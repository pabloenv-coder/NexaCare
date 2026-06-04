"""
NexaCare — Servicio de IA con Anthropic Claude + Groq (fallback gratuito) + Demo inteligente
Los chats funcionan SIEMPRE, con o sin API key.
"""
import os
import requests
import anthropic

import re

_GROQ_URL    = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL  = "llama-3.1-8b-instant"
MODEL_REPORT = "claude-sonnet-4-6"
MODEL_CHAT   = "claude-haiku-4-5-20251001"
_ANTHROPIC_TIMEOUT = 30.0

_SYSTEM = (
    "Eres NexaCare IA, un asistente médico profesional integrado en un sistema de triaje. "
    "Proporciona análisis claros, empáticos y útiles en español. "
    "Recuerda siempre que tus análisis son orientativos y no sustituyen la valoración médica."
)

_KEYWORDS: dict[str, list[str]] = {
    "Fiebre": ["fiebre", "temperatura", "calentura", "febril", "calor", "escalofr",
               "garganta", "anginas", "amígdalas", "amigdalas", "faringe", "faringitis",
               "tos", "tosiendo", "mucosidad", "mocos", "constipado"],
    "Dolor en el pecho": ["pecho", "corazon", "corazón", "cardíac", "cardiac", "angina",
                          "infarto", "torax", "tórax", "opresion", "opresión"],
    "Dolor de cabeza": ["cabeza", "cefalea", "migraña", "migrana", "jaqueca", "craneal",
                        "frente", "sien", "me duele la cabeza"],
    "Dificultad para respirar": ["respirar", "respiracion", "respiración", "ahogo", "asfixia",
                                 "aire", "disnea", "pulmón", "pulmon", "falta de aire"],
    "Malestar general": ["malestar", "cansancio", "debilidad", "agotado", "decaido", "gripe",
                         "mal cuerpo", "catarro", "resfriado", "ronquera",
                         "ronco", "picor garganta", "dolor garganta"],
    "Traumatismos y golpes": ["golpe", "caida", "caída", "trauma", "fractura", "herida",
                              "corte", "accidente", "choque", "torcedura", "esguince"],
    "Dolor abdominal": ["abdomen", "abdominal", "barriga", "estomago", "estómago", "tripa",
                        "vientre", "intestino", "nausea", "náusea", "vomit", "vómito",
                        "diarrea", "estreñimiento"],
    "Problemas urinarios": ["orinar", "orina", "riñon", "riñón", "vejiga",
                            "ardor al orinar", "miccion", "micción", "escozor"],
    "Problemas en la piel": ["piel", "erupcion", "erupción", "sarpullido",
                             "picor en la piel", "mancha", "grano", "urticaria", "eccema",
                             "ampolla", "costra", "dermatitis"],
    "Síntomas neurológicos": ["neurologico", "neurológico", "convulsion", "convulsión",
                              "parálisis", "paralisis", "hormigueo", "vértigo", "vertigo",
                              "temblor", "desmay", "epilep", "confus", "desorient",
                              "entumecimiento", "perdida de conocimiento"],
}


# ── Clientes de IA ────────────────────────────────────────────────────────────

def _client() -> anthropic.Anthropic | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            import streamlit as _st
            key = _st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    if not key or key.startswith("sk-ant-..."):
        return None
    return anthropic.Anthropic(api_key=key, timeout=_ANTHROPIC_TIMEOUT)


def _groq_key() -> str | None:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        try:
            import streamlit as _st
            key = _st.secrets.get("GROQ_API_KEY", "")
        except Exception:
            pass
    return key if key and key.startswith("gsk-") else None


def _groq_chat(system: str, user: str, max_tokens: int = 400) -> str | None:
    """Llama a Groq API usando requests. No requiere paquete adicional."""
    key = _groq_key()
    if not key:
        return None
    try:
        resp = requests.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": _GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.4,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _clean(text: str) -> str:
    """Elimina markdown del texto de respuesta IA (asteriscos, headers, etc.)."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)   # **bold**
    text = re.sub(r'\*(.+?)\*',     r'\1', text)    # *italic*
    text = re.sub(r'#{1,6}\s+',     '',    text)    # ## headers
    text = re.sub(r'^\s*[-•]\s+',   '',    text, flags=re.MULTILINE)  # bullet points
    return text.strip()


def tiene_ia() -> bool:
    """True si hay al menos una API de IA real disponible."""
    return _client() is not None or _groq_key() is not None


def tiene_ia_real() -> bool:
    """Alias de tiene_ia() para uso en app.py."""
    return tiene_ia()


# ── Informe post-triaje ────────────────────────────────────────────────────────

def generar_informe_triaje(
    sintoma: str,
    respuestas_si: list[str],
    nivel: str,
    porcentaje: int,
    edad_grupo: str | None = None,
    sexo: str | None = None,
) -> str | None:
    factores = "\n".join(f"  • {r}" for r in respuestas_si) if respuestas_si else "  • Ningún factor de riesgo adicional"
    datos_pac = ""
    if edad_grupo:
        datos_pac += f"Edad del paciente: {edad_grupo}\n"
    if sexo:
        datos_pac += f"Sexo: {sexo}\n"

    prompt = (
        f"{datos_pac}"
        f"Síntoma: {sintoma}. Nivel: {nivel} ({porcentaje}% gravedad). "
        f"Factores positivos: {', '.join(respuestas_si) if respuestas_si else 'ninguno'}.\n\n"
        "Escribe UN ÚNICO PÁRRAFO de exactamente 3-4 frases explicando: "
        "por qué se asignó este nivel, qué factores son más relevantes y qué debe hacer el paciente. "
        "PROHIBIDO: títulos, secciones, listas, asteriscos, markdown, saltos de línea extra. "
        "Solo texto corrido. Máximo 80 palabras. Tono directo y empático."
    )

    # Anthropic
    c = _client()
    if c:
        try:
            resp = c.messages.create(
                model=MODEL_REPORT,
                max_tokens=450,
                system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
            )
            return _clean(resp.content[0].text)
        except Exception:
            pass

    # Groq fallback
    r = _groq_chat(_SYSTEM, prompt, max_tokens=450)
    return _clean(r) if r else None


# ── Responder pregunta del paciente ───────────────────────────────────────────

def responder_pregunta(pregunta: str, sintoma: str, nivel: str, respuestas_si: list[str]) -> str:
    """Siempre devuelve una respuesta útil (nunca None)."""
    factores_txt = (
        "; ".join(respuestas_si) if respuestas_si else "ninguno"
    )
    user_msg = (
        f"DATOS DEL TRIAJE DE ESTE PACIENTE:\n"
        f"• Síntoma principal: {sintoma}\n"
        f"• Nivel de urgencia: {nivel}\n"
        f"• Factores de riesgo confirmados: {factores_txt}\n\n"
        f"PREGUNTA DEL PACIENTE: {pregunta}\n\n"
        "INSTRUCCIONES ESTRICTAS:\n"
        "1. Responde ESPECÍFICAMENTE para este paciente — menciona su síntoma concreto "
        "y sus factores de riesgo reales, no des consejos genéricos.\n"
        "2. Si tiene factores de riesgo, coméntalos en tu respuesta.\n"
        "3. Máximo 3 frases directas. Sin markdown, asteriscos ni listas.\n"
        "4. Empieza respondiendo directamente, sin saludos ni rodeos."
    )

    # Anthropic
    c = _client()
    if c:
        try:
            resp = c.messages.create(
                model=MODEL_CHAT,
                max_tokens=300,
                system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_msg}],
            )
            return _clean(resp.content[0].text)
        except Exception:
            pass

    # Groq fallback
    groq_resp = _groq_chat(_SYSTEM, user_msg, max_tokens=300)
    if groq_resp:
        return _clean(groq_resp)

    # Demo inteligente — siempre responde algo útil
    return _demo_respuesta(pregunta, sintoma, nivel)


def _demo_respuesta(pregunta: str, sintoma: str, nivel: str) -> str:
    """Respuestas contextuales de alta calidad sin necesitar API."""
    p = pregunta.lower()
    urgente = "ROJO" in nivel.upper() or "NARANJA" in nivel.upper()
    sint_l  = sintoma.lower()

    # Medicamentos
    if any(w in p for w in ["ibuprofeno", "paracetamol", "medicamento", "pastilla", "tomar", "analgesico", "analgésico", "antiinflamatorio", "medicina"]):
        if urgente:
            return (
                f"Con tu nivel de urgencia actual, la medicación debe ser supervisada por un profesional. "
                "No te automediques en este momento. Acude a urgencias o llama al 112 para recibir atención adecuada. "
                "El personal sanitario determinará el tratamiento más adecuado para tu situación."
            )
        if "fiebre" in sint_l:
            return (
                "Para la fiebre, el paracetamol (500–1000 mg cada 6–8 horas) es la primera opción recomendada. "
                "El ibuprofeno (400 mg cada 8 horas con comida) también es eficaz y tiene efecto antiinflamatorio. "
                "Evita el ibuprofeno si tienes el estómago delicado, embarazo o tomas anticoagulantes. "
                "Consulta a tu farmacéutico si tienes dudas sobre dosis o interacciones."
            )
        if "cabeza" in sint_l:
            return (
                "Para el dolor de cabeza, el paracetamol o el ibuprofeno suelen ser eficaces. "
                "Evita tomar más de 3 días seguidos sin consultar al médico (puede provocar cefalea por rebote). "
                "Descansa en un lugar tranquilo y oscuro, mantente hidratado. "
                "Si el dolor es muy intenso o diferente a los habituales, consulta con tu médico."
            )
        return (
            f"Para {sint_l}, consulta siempre con tu farmacéutico o médico antes de tomar medicación. "
            "El paracetamol suele ser la primera opción para el dolor leve-moderado. "
            "Respeta siempre la dosis indicada y el intervalo entre tomas. "
            "Si tienes alguna enfermedad crónica o tomas otros medicamentos, infórmale siempre."
        )

    # Cuándo ir al médico/urgencias
    if any(w in p for w in ["hospital", "urgencias", "urgencia", "medico", "médico", "doctor", "ir", "cuándo", "cuando", "necesito"]):
        if urgente:
            return (
                f"Con tu nivel de urgencia ({nivel}), deberías acudir a urgencias hospitalarias lo antes posible. "
                "No esperes a que los síntomas empeoren. Si notas dificultad para respirar, dolor intenso o pérdida de consciencia, llama al 112 de inmediato. "
                "Lleva este informe de NexaCare para informar al personal sanitario."
            )
        return (
            f"Con tu nivel actual ({nivel}), puedes esperar cita con tu médico de cabecera en las próximas horas o días. "
            "Ve a urgencias si los síntomas empeoran de repente, si aparece fiebre alta (>39°C), "
            "dificultad para respirar, confusión o dolor muy intenso. "
            "En caso de duda, llama al 061 para orientación sanitaria telefónica gratuita."
        )

    # Reposo
    if any(w in p for w in ["reposo", "descanso", "cama", "dormir", "actividad", "trabajar", "ejercicio", "deporte"]):
        if urgente:
            return (
                f"Con tu nivel de urgencia, el reposo absoluto es importante. "
                "Evita cualquier esfuerzo físico hasta recibir valoración médica. "
                "Mantente cómodo, bien hidratado y pide ayuda si lo necesitas."
            )
        return (
            f"El reposo es clave para recuperarte de {sint_l}. "
            "Descansa lo que tu cuerpo necesite, especialmente las primeras 24-48 horas. "
            "Evita el ejercicio intenso hasta sentirte claramente mejor. "
            "Puedes retomar la actividad de forma gradual cuando los síntomas mejoren significativamente."
        )

    # Alimentación e hidratación
    if any(w in p for w in ["comer", "beber", "agua", "dieta", "alimentación", "alimentacion", "hidrat", "liquido", "líquido", "nausea", "náusea", "vomito", "vómito"]):
        if "abdominal" in sint_l or "nausea" in sint_l or "vomit" in sint_l:
            return (
                "Con síntomas digestivos, opta por la dieta BRAT: plátano, arroz, manzana y tostadas. "
                "Bebe líquidos a pequeños sorbos frecuentes (agua, suero oral, infusiones suaves). "
                "Evita lácteos, fritos, picantes y alcohol hasta la recuperación completa. "
                "Si no toleras nada por vía oral durante más de 24 horas, consulta al médico."
            )
        return (
            "Mantente bien hidratado bebiendo agua con frecuencia (1.5–2 litros al día). "
            "Come de forma ligera y equilibrada; prioriza frutas, verduras y proteínas magras. "
            "Evita el alcohol, el tabaco y los alimentos muy procesados durante la recuperación. "
            "Si tienes fiebre, aumenta la ingesta de líquidos para compensar la pérdida por sudoración."
        )

    # Contagio
    if any(w in p for w in ["contagio", "contagiar", "transmit", "infectar", "contagioso"]):
        return (
            f"La transmisión de {sint_l} depende de la causa específica, que solo puede determinar un médico. "
            "Como medida preventiva general: lávate las manos frecuentemente con agua y jabón, "
            "cubre la boca al toser o estornudar, ventila bien los espacios y evita contacto cercano "
            "con personas vulnerables (mayores, embarazadas, inmunodeprimidos) hasta que mejores."
        )

    # Duración / cuánto tiempo
    if any(w in p for w in ["cuánto", "cuanto", "tiempo", "días", "dias", "semana", "dura", "tardará", "tardara"]):
        if urgente:
            return (
                f"Con tu nivel de urgencia, la duración del proceso dependerá del diagnóstico médico. "
                "No puedo estimarla sin una valoración profesional. Lo importante ahora es recibir atención médica pronto."
            )
        return (
            f"La duración de {sint_l} varía según la causa subyacente. "
            "Los síntomas leves suelen mejorar en 3-7 días con reposo y cuidados adecuados. "
            "Si no hay mejoría en 48-72 horas, o si los síntomas empeoran, consulta con tu médico. "
            "Un diagnóstico preciso es necesario para dar una estimación fiable."
        )

    # Temperatura / fiebre
    if any(w in p for w in ["temperatura", "grados", "termómetro", "termometro", "37", "38", "39", "40"]):
        return (
            "La fiebre se considera desde 37.5°C. Grados orientativos: "
            "37.5–38°C febrícula (reposo y vigilancia), 38–39°C fiebre moderada (antitérmico si hay malestar), "
            "39–40°C fiebre alta (antitérmico y vigilancia estrecha), >40°C fiebre muy alta (urgencias). "
            "Mide la temperatura en reposo, sin ropa de abrigo y espera 30 min tras actividad física."
        )

    # Respuesta genérica contextual
    if urgente:
        return (
            f"Con tu nivel de urgencia ({nivel}) y los síntomas de {sint_l}, "
            "la consulta más importante es con un profesional sanitario. "
            "Llama al 061 para orientación telefónica gratuita o acude a urgencias. "
            "Si notas empeoramiento brusco, llama al 112."
        )
    return (
        f"Para resolver tu duda sobre {sint_l}, te recomiendo consultar con tu médico de cabecera "
        "o llamar al 061 (urgencias sanitarias) para orientación telefónica gratuita. "
        f"Con tu nivel actual ({nivel}), puedes hacer seguimiento en casa y acudir al médico "
        "si los síntomas persisten más de 48 horas o se intensifican."
    )


# ── Clasificación de síntoma por texto libre ──────────────────────────────────

def _clasificar_keywords(texto: str) -> str | None:
    t = texto.lower()
    best, best_score = None, 0
    for sintoma, kws in _KEYWORDS.items():
        score = sum(1 for kw in kws if kw in t)
        if score > best_score:
            best_score, best = score, sintoma
    return best if best_score > 0 else None


def clasificar_sintoma(texto: str, opciones: list[str]) -> tuple[str | None, str]:
    """Devuelve (sintoma_detectado, metodo) donde metodo es 'IA' o 'reglas'."""
    lista  = "\n".join(f"- {o}" for o in opciones)
    prompt = (
        f'El paciente dice: "{texto}"\n\n'
        f"Elige la categoría más adecuada de esta lista exacta:\n{lista}\n\n"
        "IMPORTANTE: Responde SOLO con el texto exacto de una categoría, sin nada más. "
        "Si menciona garganta, anginas o tos → responde 'Fiebre'. "
        "Si menciona barriga, estómago, vómitos → responde 'Dolor abdominal'. "
        "Copia el texto exactamente como aparece en la lista."
    )

    # Anthropic
    c = _client()
    if c:
        try:
            resp = c.messages.create(
                model=MODEL_CHAT,
                max_tokens=60,
                system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
            )
            texto_resp = resp.content[0].text.strip()
            if texto_resp in opciones:
                return texto_resp, "IA"
            for op in opciones:
                if op.lower() in texto_resp.lower() or texto_resp.lower() in op.lower():
                    return op, "IA"
        except Exception:
            pass

    # Groq fallback
    groq_resp = _groq_chat(_SYSTEM, prompt, max_tokens=60)
    if groq_resp:
        groq_resp = groq_resp.strip()
        if groq_resp in opciones:
            return groq_resp, "IA"
        for op in opciones:
            if op.lower() in groq_resp.lower() or groq_resp.lower() in op.lower():
                return op, "IA"

    # Keywords fallback
    return _clasificar_keywords(texto), "reglas"
