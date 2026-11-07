"""Lecture de la fiche papier par un modèle de vision (API Claude) + extraction des images d'un Excel."""
import base64, io, json, zipfile

MODELE = "claude-sonnet-5-5"        # modèle Claude (payant)
MODELE_GEMINI = "gemini-2.5-flash"   # modèle Gemini (niveau gratuit, vérifier dans Google AI Studio)

PROMPT = """Tu lis la photo d'une fiche papier de chantier ferroviaire (« fiche de chambre »).
Elle contient un cadre par masque (A, B, C, D). Dans chaque masque, l'opérateur a dessiné des CERCLES
(un cercle = un fourreau). Dans chaque cercle : « V » = vide, ou un pourcentage (20%, 65%...) = taux de remplissage.
Une flèche avec un nombre (ex. ↓0,59) donne la profondeur GS en mètres. Une petite annotation près des cercles
peut donner le diamètre (ex. Ø100) et le matériau (ex. TPC, PVC).

Réponds UNIQUEMENT par un objet JSON, sans texte autour, de cette forme :
{
 "chambre": "F57",
 "dimensions": "1,26*1,26*0,82",
 "remarque": "texte de la zone Remarque s'il y en a un",
 "masques": {
   "A": {"gs": 0.59, "diam_texte": "Ø100(TPC)",
         "fourreaux": [{"etat": "20%", "col": 0, "ligne": 0, "diametre": 100}]},
   "B": {"fourreaux": []}, "C": {...}, "D": {"fourreaux": []}
 },
 "incertitudes": ["liste courte de tout ce que tu n'as pas pu lire avec certitude"]
}
Règles :
- col = position horizontale du cercle dans le masque (0, 1, 2... de gauche à droite), ligne = rangée (0, 1... de haut en bas).
  Respecte les alignements : deux cercles côte à côte ont la même ligne, deux cercles empilés la même col.
- diametre en millimètres (nombre) ; si non lisible, mets 100 et signale-le dans incertitudes.
- Un masque sans cercle a une liste « fourreaux » vide. Omet « gs » s'il n'y a pas de flèche.
- N'invente rien : en cas de doute, écris ta meilleure lecture ET mentionne le doute dans « incertitudes ».
"""

def images_du_xlsx(xlsx_bytes):
    """Renvoie [(nom, octets)] pour les images intégrées à l'Excel (photos Kizeo)."""
    z = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    return [(n, z.read(n)) for n in sorted(z.namelist()) if n.startswith("xl/media/")]

def type_image(b):
    if b[:3] == b"\xff\xd8\xff": return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n": return "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "image/webp"
    return None

def extraire_json(texte):
    """Extrait le premier objet JSON d'une réponse (tolère les ```json)."""
    d, f = texte.find("{"), texte.rfind("}")
    if d < 0 or f < d:
        raise ValueError("Réponse sans JSON exploitable")
    return json.loads(texte[d:f + 1])

def lire_fiche_gemini(image_bytes, api_key, mt):
    import urllib.request, urllib.error
    corps = {"contents": [{"parts": [
                {"inline_data": {"mime_type": mt, "data": base64.b64encode(image_bytes).decode()}},
                {"text": PROMPT}]}],
             "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODELE_GEMINI}:generateContent",
        data=json.dumps(corps).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            rep = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini a refusé la requête (code {e.code}) : {e.read().decode()[:300]}")
    parts = rep["candidates"][0]["content"]["parts"]
    return extraire_json("".join(p.get("text", "") for p in parts))

def lire_fiche(image_bytes, api_key, fournisseur="gemini"):
    mt = type_image(image_bytes)
    if not mt:
        raise ValueError("Format d'image non reconnu (JPEG, PNG ou WEBP attendus)")
    if fournisseur == "gemini":
        return lire_fiche_gemini(image_bytes, api_key, mt)
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    rep = client.messages.create(
        model=MODELE, max_tokens=2500,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mt,
                                         "data": base64.b64encode(image_bytes).decode()}},
            {"type": "text", "text": PROMPT}]}])
    return extraire_json("".join(b.text for b in rep.content if b.type == "text"))
