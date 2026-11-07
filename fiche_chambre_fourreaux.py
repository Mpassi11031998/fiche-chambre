#!/usr/bin/env python3
"""Prototype : dessine les fourreaux (cercles) dans les schémas de masques d'une fiche de chambre brute.
Usage : python fiche_chambre_fourreaux.py fiche_brute.xlsx saisie.json fiche_traitee.xlsx
Ne touche qu'à xl/drawings/drawing1.xml : mise en page, photos et styles restent intacts."""
import sys, json, zipfile, re
from xml.sax.saxutils import escape

# --- Réglages (modifiables) -------------------------------------------------
EMU_COL = 291000      # largeur d'une colonne de la grille (EMU)
EMU_ROW = 171450      # hauteur d'une ligne de la grille (EMU)
BASE = 350000         # diamètre du cercle pour un Ø100 (EMU, ~1 cm)
# Échelle : diamètre réel (mm) -> coefficient (Ø100 = 1.0 ; Ø200 = 1.3, "un peu plus grand")
ECHELLE = [(45, .60), (60, .75), (80, .90), (100, 1.0), (150, 1.15), (200, 1.30), (300, 1.6)]
# Coin haut-gauche (colonne, ligne, base 0) de la grille de chaque masque dans le modèle brut
ORIGINE = {"A": (17, 19), "B": (31, 28), "D": (3, 28), "C": (17, 43)}
PAS_X, PAS_Y = 1.6, 2.4   # pas entre deux cercles (en cellules)

def coef(d):
    pts = ECHELLE
    if d <= pts[0][0]: return pts[0][1]
    for (d0, c0), (d1, c1) in zip(pts, pts[1:]):
        if d <= d1: return c0 + (c1 - c0) * (d - d0) / (d1 - d0)
    return pts[-1][1]

def anchor(col, row, dx, dy, cx, cy):
    """Convertit une position en cellules (flottante) en ancre Excel."""
    c = col + dx; r = row + dy
    ci, ri = int(c), int(r)
    return (f"<xdr:from><xdr:col>{ci}</xdr:col><xdr:colOff>{int((c-ci)*EMU_COL)}</xdr:colOff>"
            f"<xdr:row>{ri}</xdr:row><xdr:rowOff>{int((r-ri)*EMU_ROW)}</xdr:rowOff></xdr:from>"
            f'<xdr:ext cx="{int(cx)}" cy="{int(cy)}"/>')

def shape(i, name, geom, txt, pos, size, border=True, bold=True, sz=700):
    ln = '<a:ln w="12700"><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln>' if border else '<a:ln><a:noFill/></a:ln>'
    fill = '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>' if border else '<a:noFill/>'
    box = '' if border else ' txBox="1"'
    algn = 'ctr' if border else 'l'
    return (f"<xdr:oneCellAnchor>{pos}<xdr:sp macro=\"\" textlink=\"\"><xdr:nvSpPr>"
            f'<xdr:cNvPr id="{i}" name="{escape(name)}"/><xdr:cNvSpPr{box}/></xdr:nvSpPr>'
            f'<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{int(size[0])}" cy="{int(size[1])}"/></a:xfrm>'
            f'<a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>{fill}{ln}</xdr:spPr>'
            f'<xdr:txBody><a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"/><a:lstStyle/>'
            f'<a:p><a:pPr algn="{algn}"/><a:r><a:rPr lang="fr-FR" sz="{sz}" b="{int(bold)}"/><a:t>{escape(txt)}</a:t></a:r></a:p>'
            f"</xdr:txBody></xdr:sp><xdr:clientData/></xdr:oneCellAnchor>")

def build(saisie):
    out, uid = [], 100
    for m, data in saisie["masques"].items():
        ox, oy = ORIGINE[m]
        for f in data["fourreaux"]:
            d = f.get("diametre", 100)
            s = BASE * coef(d)
            x = ox + 0.4 + f["col"] * PAS_X
            y = oy + 0.5 + f["ligne"] * PAS_Y
            uid += 1
            out.append(shape(uid, f"Fourreau {m}{uid}", "ellipse", f["etat"], anchor(int(x), int(y), x-int(x), y-int(y), s, s), (s, s)))
        # textes : profondeur (GS) et diamètre/matériau, sous le masque
        ligne_txt = oy + 0.3
        for k, t in enumerate([f"GS:{data['gs']}" if "gs" in data else "", data.get("diam_texte", "")]):
            if t:
                uid += 1
                px = ox + 10.3 if m != 'D' else ox + 0.2; py = (oy + 1.0 + k * 1.0) if m != 'D' else (oy + 9.0 + k * 1.0)
                out.append(shape(uid, f"Texte {m}{uid}", "rect", t, anchor(int(px), int(py), px-int(px), py-int(py), 1300000, 150000), (1300000, 150000), border=False, bold=False, sz=700))
    return "".join(out)

def traiter(xlsx_bytes, saisie):
    """Version mémoire (pour l'application web) : renvoie les octets du fichier traité."""
    import io
    zin = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    buf = io.BytesIO()
    zout = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
    for it in zin.infolist():
        data = zin.read(it.filename)
        if it.filename == "xl/drawings/drawing1.xml":
            t = data.decode("utf-8").replace("</xdr:wsDr>", build(saisie) + "</xdr:wsDr>")
            data = t.encode("utf-8")
        zout.writestr(it, data)
    zout.close()
    return buf.getvalue()

def main(src, js, dst):
    saisie = json.load(open(js, encoding="utf-8"))
    zin = zipfile.ZipFile(src)
    zout = zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED)
    for it in zin.infolist():
        data = zin.read(it.filename)
        if it.filename == "xl/drawings/drawing1.xml":
            t = data.decode("utf-8")
            t = t.replace("</xdr:wsDr>", build(saisie) + "</xdr:wsDr>")
            data = t.encode("utf-8")
        zout.writestr(it, data)
    zout.close()

if __name__ == "__main__":
    main(*sys.argv[1:4])
