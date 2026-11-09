"""Document sources. All access is READ-ONLY.
 - LocalFolderSource: a folder tree (mock Drive / a Drive-for-desktop synced folder / downloaded copy)
 - GoogleDriveSource: Drive API v3 with the drive.readonly scope (only list/get/export calls)"""
import os, re, io
from datetime import datetime, timezone
from pathlib import Path

TEXT_EXT = {".md", ".txt", ".markdown"}
VER_RE = re.compile(r"^(?P<base>.*?)[ _\-]*[vV]?(?P<ver>\d+(?:\.\d+)*)$")
VER_TAG_RE = re.compile(r"^(?P<base>.+?)[ _\-]+[vV](?P<ver>\d+(?:\.\d+)*)(?:[ _\-]+[A-Za-z]+)*$")  # Policy_Expense_v2_Current


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def split_name(stem):
    """'SRS_v2' -> ('SRS','v2'); no version suffix -> (stem, None)."""
    m = VER_TAG_RE.match(stem) or VER_RE.match(stem)
    if m and m.group("base"):
        return m.group("base"), "v" + m.group("ver")
    return stem, None


class LocalFolderSource:
    def __init__(self, root, name="local"):
        self.root = Path(root); self.name = name

    def _manifest(self):
        m = self.root / "MANIFEST.json"
        if not m.exists(): return {}
        import json
        return {f["snapshot"]: f for f in json.loads(m.read_text(encoding="utf-8")).get("files", [])}

    def _index(self):
        docs, man = {}, self._manifest()
        for p in sorted(self.root.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in TEXT_EXT: continue
            if p.parent != self.root:
                doc, label = p.parent.name, p.stem
            else:
                doc, label = split_name(p.stem)
                label = label or "current"
            st = p.stat()
            docs.setdefault(doc, []).append({
                "id": label, "label": label, "file": p.name, "ref": str(p),
                "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                "size": st.st_size,
                "origin": man.get(p.name, {}).get("origin", "unknown"), "drive_id": man.get(p.name, {}).get("drive_id")})
        for v in docs.values(): v.sort(key=lambda x: natural_key(x["id"]))
        return docs

    def documents(self):
        return [{"name": d, "versions": v} for d, v in sorted(self._index().items())]

    def versions(self, doc):
        return self._index().get(doc, [])

    def read_text(self, doc, version_id):
        for v in self.versions(doc):
            if v["id"] == version_id:
                return Path(v["ref"]).read_text(encoding="utf-8")  # read-only access
        raise KeyError(f"{doc}:{version_id}")


class GoogleDriveSource:
    """Read-only Drive API v3 adapter. Needs: pip install google-api-python-client google-auth
    Auth: service account JSON (folder shared with its e-mail) via GOOGLE_APPLICATION_CREDENTIALS.
    Version discovery: (1) native Drive revisions of Google Docs, (2) name-based grouping
    ('SRS_v1.docx', 'SRS_v2.docx'), (3) sub-folders = one document, files inside = versions."""
    name = "gdrive"
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    FOLDER = "application/vnd.google-apps.folder"
    GDOC = "application/vnd.google-apps.document"

    def __init__(self, folder_id, credentials_file=None, service=None):
        self.folder_id = folder_id
        if service is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            creds = service_account.Credentials.from_service_account_file(
                credentials_file or os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=self.SCOPES)
            service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.svc = service
        self._cache = None

    def _list(self, parent):
        out, tok = [], None
        while True:
            r = self.svc.files().list(q=f"'{parent}' in parents and trashed=false", pageToken=tok,
                                      fields="nextPageToken, files(id,name,mimeType,modifiedTime,size)",
                                      supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            out += r.get("files", []); tok = r.get("nextPageToken")
            if not tok: return out

    def _index(self):
        if self._cache: return self._cache
        docs = {}
        def add(doc, v): docs.setdefault(doc, []).append(v)
        for f in self._list(self.folder_id):
            if f["mimeType"] == self.FOLDER:
                for g in self._list(f["id"]):
                    add(f["name"], self._v(g, Path(g["name"]).stem))
            elif f["mimeType"] == self.GDOC:
                revs = self.svc.revisions().list(fileId=f["id"], fields="revisions(id,modifiedTime)").execute().get("revisions", [])
                for n, r in enumerate(revs, 1):
                    add(f["name"], {"id": f"r{n}", "label": f"revision {n}", "file": f["name"], "modified": r["modifiedTime"],
                                    "ref": {"file_id": f["id"], "mime": f["mimeType"], "revision_id": r["id"]}})
            else:
                base, label = split_name(Path(f["name"]).stem)
                add(base, self._v(f, label or Path(f["name"]).stem))
        for v in docs.values():
            v.sort(key=lambda x: [int(x["id"][1:])] if re.fullmatch(r"r\d+", x["id"]) else natural_key(x["id"]))
        self._cache = docs
        return docs

    def _v(self, f, label):
        return {"id": label, "label": label, "file": f["name"], "modified": f.get("modifiedTime"),
                "ref": {"file_id": f["id"], "mime": f["mimeType"], "revision_id": None}}

    def documents(self): return [{"name": d, "versions": v} for d, v in sorted(self._index().items())]
    def versions(self, doc): return self._index().get(doc, [])

    def read_text(self, doc, version_id):
        v = next(x for x in self.versions(doc) if x["id"] == version_id)
        ref = v["ref"]
        if ref["revision_id"]:
            from google.auth.transport.requests import AuthorizedSession
            rev = self.svc.revisions().get(fileId=ref["file_id"], revisionId=ref["revision_id"], fields="exportLinks").execute()
            return AuthorizedSession(self.svc._http.credentials).get(rev["exportLinks"]["text/plain"]).text
        if ref["mime"] == self.GDOC:
            return self.svc.files().export(fileId=ref["file_id"], mimeType="text/plain").execute().decode("utf-8")
        data = self.svc.files().get_media(fileId=ref["file_id"]).execute()
        if v["file"].lower().endswith(".docx"):
            from docx import Document  # optional: pip install python-docx
            return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        return data.decode("utf-8", "replace")


def make_source():
    if os.environ.get("DRIVE_SOURCE", "snapshot") == "gdrive":
        return GoogleDriveSource(os.environ["GDRIVE_FOLDER_ID"])
    base = Path(__file__).resolve().parent.parent
    if os.environ.get("DRIVE_SOURCE", "snapshot") == "mock":
        return LocalFolderSource(os.environ.get("MOCK_DRIVE_DIR", base / "mock_drive"), "mock")
    return LocalFolderSource(os.environ.get("SNAPSHOT_DIR", base / "drive_snapshot"), "snapshot")
