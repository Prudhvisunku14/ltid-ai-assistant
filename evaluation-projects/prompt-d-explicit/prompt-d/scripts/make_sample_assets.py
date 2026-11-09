"""Regenerates data/drive_mock/website_spec.docx (a MOCK of a Drive file) using only zipfile."""
import sys, zipfile
from xml.sax.saxutils import escape
from pathlib import Path

PARAS = [
    "Acme Bakery website change specification (MOCK Drive document)",
    "REQ-1: Add a Contact page (contact.html) and link it from the navigation on every page.",
    "REQ-2: The contact form must have required name, email and message fields with client-side validation and accessible error messages.",
    "REQ-3: Add a dark mode toggle button in the header; the choice must persist between visits.",
    "REQ-4: Every page must declare a language, have a unique title, and provide a skip-to-content link.",
]


def write_docx(path, paras):
    body = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(p)}</w:t></w:r></w:p>" for p in paras)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           + body + "</w:body></w:document>")
    ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct); z.writestr("_rels/.rels", rels); z.writestr("word/document.xml", doc)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data/drive_mock/website_spec.docx")
    write_docx(out, PARAS); print("wrote", out)
